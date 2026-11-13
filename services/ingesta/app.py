"""API de ingesta de pedidos de Salomé (FastAPI).

Recibe pedidos como CSV o como JSON, los guarda tal cual en raw/ y publica un mensaje
en la cola. Responde 202 en cuanto el archivo quedó guardado: la limpieza la hace el
worker después, así Salomé no se queda esperando.

Documentación interactiva (OpenAPI): http://<servidor>:8000/docs

Variables de entorno: BUCKET, QUEUE_URL, DATABASE_URL, AWS_REGION,
AWS_PROFILE=ingesta en el servidor, AWS_ENDPOINT_URL solo en pruebas locales.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

import boto3
import psycopg2
from botocore.exceptions import BotoCoreError, ClientError
import hmac

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

log = logging.getLogger("ingesta")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

COLUMNAS = ["pedido_id", "cliente_id", "fecha_pedido", "hora_pedido", "fecha_entrega", "producto",
            "categoria", "unidades", "precio_unitario", "total", "canal", "entrega", "metodo_pago"]
MAX_BYTES = int(os.getenv("MAX_BYTES", str(5 * 1024 * 1024)))
MAX_RENGLONES = int(os.getenv("MAX_RENGLONES", "50000"))
TOPE_TEXTO = 120

TOKEN = os.getenv("INGESTA_TOKEN", "")


def autorizar(x_api_key: str | None = Header(default=None, description="Llave de la ingesta (obligatoria en la nube)")):
    """Con la API publicada en internet (ECS), solo quien tenga la llave puede subir pedidos.
    En local, sin INGESTA_TOKEN definido, la revisión se omite."""
    if TOKEN and not (x_api_key and hmac.compare_digest(x_api_key, TOKEN)):
        raise HTTPException(401, "Falta la llave o no es válida (encabezado X-Api-Key).")


app = FastAPI(
    title="Salomé · API de ingesta",
    version="2.0.0",
    description=("Recibe los pedidos de Salomé (CSV o JSON), los guarda sin tocar en `raw/` del data lake "
                 "y avisa al worker por la cola SQS. La limpieza ocurre de forma asíncrona; el estado de cada "
                 "carga se consulta en `GET /cargas/{carga_id}`."),
)


class LineaPedido(BaseModel):
    """Un renglón tal como Salomé lo captura. Se aceptan textos porque raw/ guarda los datos como llegan;
    el worker se encarga de corregirlos."""
    pedido_id: int = Field(gt=0, examples=[8001])
    cliente_id: str = Field(min_length=1, max_length=20, pattern=r"^C\d{3,6}$", examples=["C0042"])
    fecha_pedido: str = Field(max_length=20, examples=["2026-11-03"])
    hora_pedido: str | None = Field(default=None, max_length=8, examples=["20:41"])
    fecha_entrega: str = Field(max_length=20, examples=["2026-11-05"])
    producto: str = Field(min_length=2, max_length=TOPE_TEXTO, examples=["Cheesecake frutos rojos entero"])
    categoria: str = Field(max_length=TOPE_TEXTO, examples=["Pasteles enteros"])
    unidades: str | int = Field(examples=[1])
    precio_unitario: float | None = Field(default=None, ge=0, le=20000, examples=[590])
    total: float | None = Field(default=None, ge=0, le=100000, examples=[590])
    canal: str = Field(max_length=20, examples=["WhatsApp"])
    entrega: str = Field(max_length=20, examples=["Domicilio"])
    metodo_pago: str = Field(max_length=20, examples=["Transferencia"])


class CargaAceptada(BaseModel):
    carga_id: str
    estado: Literal["recibida"]
    s3_key: str
    renglones: int
    mensaje: str


class EstadoCarga(BaseModel):
    carga_id: str
    estado: str
    recibida_en: datetime
    procesada_en: datetime | None
    registros_crudos: int | None
    registros_limpios: int | None
    intentos: int
    reporte: dict | None
    error: str | None


def _s3():
    return boto3.client("s3")


def _sqs():
    return boto3.client("sqs")


def _db():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def _validar_csv(contenido: bytes) -> int:
    if len(contenido) == 0:
        raise HTTPException(400, "El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise HTTPException(413, f"El archivo pesa más de {MAX_BYTES // 1024 // 1024} MB.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo debe estar en UTF-8 (en Excel: Guardar como > CSV UTF-8).")
    lector = csv.reader(io.StringIO(texto))
    try:
        encabezado = [c.strip() for c in next(lector)]
    except StopIteration:
        raise HTTPException(400, "El archivo no tiene encabezado.")
    faltan = [c for c in COLUMNAS if c not in encabezado]
    if faltan:
        raise HTTPException(422, {"error": "Faltan columnas", "faltan": faltan, "esperadas": COLUMNAS})
    pos = encabezado.index("pedido_id")
    n = 0
    for i, fila in enumerate(lector, start=2):
        if not any(c.strip() for c in fila):
            continue
        if len(fila) != len(encabezado):
            raise HTTPException(422, f"El renglón {i} tiene {len(fila)} columnas y el encabezado {len(encabezado)}.")
        if not fila[pos].strip().isdigit():
            raise HTTPException(422, f"El renglón {i} no tiene un pedido_id numérico.")
        if any(len(c) > TOPE_TEXTO for c in fila):
            raise HTTPException(422, f"El renglón {i} tiene un valor de más de {TOPE_TEXTO} caracteres.")
        n += 1
        if n > MAX_RENGLONES:
            raise HTTPException(413, f"Máximo {MAX_RENGLONES} renglones por carga.")
    if n == 0:
        raise HTTPException(400, "El archivo no trae renglones.")
    return n


def _registrar(contenido: bytes, renglones: int, origen: str) -> CargaAceptada:
    bucket, cola = os.environ["BUCKET"], os.environ["QUEUE_URL"]
    carga_id = str(uuid.uuid4())
    ahora = datetime.now(timezone.utc)
    key = f"raw/pedidos/fecha_carga={ahora:%Y-%m-%d}/{carga_id}.csv"

    try:  # 1) el archivo crudo, inmutable
        _s3().put_object(Bucket=bucket, Key=key, Body=contenido, ContentType="text/csv",
                         Metadata={"carga_id": carga_id, "origen": origen})
    except (ClientError, BotoCoreError) as e:
        log.exception("no se pudo guardar en S3")
        raise HTTPException(503, "No se pudo guardar el archivo; intenta de nuevo en un momento.") from e

    try:  # 2) registro de la carga para poder consultar su estado
        with _db() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cargas (carga_id, s3_key, origen, recibida_en, estado) VALUES (%s,%s,%s,%s,'recibida')",
                        (carga_id, key, origen, ahora))
        conn.close()
    except psycopg2.Error:
        log.exception("no se pudo registrar la carga en la base; el worker la registrará igual")

    try:  # 3) aviso al worker
        _sqs().send_message(QueueUrl=cola, MessageBody=json.dumps(
            {"carga_id": carga_id, "bucket": bucket, "key": key, "recibida_en": ahora.isoformat(), "renglones": renglones}))
    except (ClientError, BotoCoreError) as e:
        log.exception("el archivo quedó en raw/ pero no se pudo avisar a la cola")
        raise HTTPException(503, f"El archivo quedó guardado ({key}) pero no se pudo encolar; vuelve a enviarlo.") from e

    return CargaAceptada(carga_id=carga_id, estado="recibida", s3_key=key, renglones=renglones,
                         mensaje="Recibido. Consulta GET /cargas/{carga_id}; normalmente queda listo en segundos.")


@app.get("/salud", summary="Revisa que la API esté viva")
def salud():
    return {"estado": "ok", "hora": datetime.now(timezone.utc).isoformat()}


@app.post("/pedidos/csv", status_code=status.HTTP_202_ACCEPTED, response_model=CargaAceptada,
          summary="Sube un CSV de pedidos",
          responses={401: {"description": "Falta la llave X-Api-Key"}, 400: {"description": "Archivo vacío o mal codificado"}, 413: {"description": "Archivo demasiado grande"},
                     422: {"description": "Faltan columnas o hay renglones mal formados"}, 503: {"description": "Falla temporal de la nube"}})
async def subir_csv(archivo: UploadFile = File(..., description="CSV con las 13 columnas del diccionario de datos"),
                    _: None = Depends(autorizar)):
    contenido = await archivo.read(MAX_BYTES + 1)
    n = _validar_csv(contenido)
    return _registrar(contenido, n, "csv")


@app.post("/pedidos", status_code=status.HTTP_202_ACCEPTED, response_model=CargaAceptada,
          summary="Envía pedidos como JSON", responses={422: {"description": "Algún campo no pasa la validación"}})
def subir_json(lineas: list[LineaPedido], _: None = Depends(autorizar)):
    if not lineas:
        raise HTTPException(400, "La lista de pedidos está vacía.")
    if len(lineas) > MAX_RENGLONES:
        raise HTTPException(413, f"Máximo {MAX_RENGLONES} renglones por carga.")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS)
    w.writeheader()
    for l in lineas:
        w.writerow(l.model_dump())
    return _registrar(buf.getvalue().encode("utf-8"), len(lineas), "json")


@app.get("/cargas/{carga_id}", response_model=EstadoCarga, summary="Estado de una carga",
         responses={404: {"description": "No existe esa carga"}})
def estado(carga_id: uuid.UUID, _: None = Depends(autorizar)):
    with _db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT carga_id::text, estado, recibida_en, procesada_en, registros_crudos, registros_limpios,
                              intentos, reporte, error FROM cargas WHERE carga_id = %s""", (str(carga_id),))
        fila = cur.fetchone()
    conn.close()
    if not fila:
        raise HTTPException(404, "No existe esa carga.")
    campos = ["carga_id", "estado", "recibida_en", "procesada_en", "registros_crudos", "registros_limpios",
              "intentos", "reporte", "error"]
    return EstadoCarga(**dict(zip(campos, fila)))
