"""Worker de limpieza: consume la cola, limpia y escribe en clean/ y en PostgreSQL.

Cada mensaje de la cola dice qué archivo llegó a raw/. El worker:
  1. descarga el archivo crudo de raw/
  2. lo limpia con limpieza.py y valida el resultado
  3. escribe la versión limpia de esa carga y actualiza el consolidado en clean/
  4. guarda los pedidos en PostgreSQL (transacción única, sin duplicar si se repite)
  5. borra el mensaje de la cola SOLO si todo salió bien

Si algo falla, el mensaje no se borra: SQS lo vuelve a entregar cuando vence el
tiempo de visibilidad (reintento). Después de 3 intentos fallidos SQS lo manda a la
cola de mensajes fallidos (DLQ) para revisarlo a mano.

Variables de entorno:
  BUCKET, QUEUE_URL, DATABASE_URL, AWS_REGION (o AWS_DEFAULT_REGION)
  AWS_PROFILE=worker en el servidor (rol de mínimo privilegio)
  AWS_ENDPOINT_URL solo para pruebas locales con moto
"""
from __future__ import annotations

import io
import json
import logging
import os
import signal
import sys
import time

import boto3
import pandas as pd
from botocore.exceptions import ClientError

import db
from limpieza import cargar_catalogo, limpiar, validar_limpio

log = logging.getLogger("worker")
CONSOLIDADO = "clean/pedidos/pedidos_salome_clean.csv"
ESPERA = int(os.getenv("ESPERA_COLA", "20"))          # long polling: menos llamadas, menos costo
VISIBILIDAD = int(os.getenv("VISIBILIDAD", "120"))
_detener = False


class ErrorDeDatos(Exception):
    """El archivo no se puede limpiar. Reintentar no lo arregla, pero se deja a la DLQ para revisarlo."""


def _leer_csv(s3, bucket: str, key: str) -> pd.DataFrame | None:
    try:
        cuerpo = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise
    return pd.read_csv(io.BytesIO(cuerpo), dtype=str, keep_default_na=True)


def _escribir_csv(s3, bucket: str, key: str, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False, date_format="%Y-%m-%d")
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")


def procesar(mensaje: dict, s3, conn, bucket: str, catalogo: pd.DataFrame) -> dict:
    inicio = time.time()
    carga_id, key = mensaje["carga_id"], mensaje["key"]
    if not key.startswith("raw/"):
        raise ErrorDeDatos(f"la llave {key} no está en raw/")
    db.asegurar_carga(conn, carga_id, key)
    db.marcar(conn, carga_id, "procesando")
    crudo = _leer_csv(s3, bucket, key)
    if crudo is None:
        raise ErrorDeDatos(f"no existe {key}")
    try:
        limpio, rep = limpiar(crudo, catalogo)
    except ValueError as e:
        raise ErrorDeDatos(str(e)) from e
    problemas = validar_limpio(limpio)
    if problemas:
        raise ErrorDeDatos("; ".join(problemas))

    _escribir_csv(s3, bucket, f"clean/pedidos/cargas/{carga_id}.csv", limpio)
    actual = _leer_csv(s3, bucket, CONSOLIDADO)
    if actual is not None:
        actual, _ = limpiar(actual, catalogo)  # ya está limpio; esto solo regresa los tipos
        # si un pedido llega de nuevo, su versión nueva reemplaza todos sus renglones
        nuevos = set(limpio.pedido_id)
        todo = pd.concat([actual[~actual.pedido_id.isin(nuevos)], limpio])
    else:
        todo = limpio
    todo = todo.sort_values(["fecha_pedido", "pedido_id", "producto"])
    _escribir_csv(s3, bucket, CONSOLIDADO, todo)

    n = db.guardar_pedidos(conn, limpio, carga_id)
    resumen = rep.como_dict() | {"renglones_en_bd": n, "segundos": round(time.time() - inicio, 2)}
    db.marcar(conn, carga_id, "procesada", procesada_en=pd.Timestamp.now(tz="UTC").to_pydatetime(),
              registros_crudos=rep.crudos, registros_limpios=rep.limpios, reporte=resumen, error=None)
    return resumen


def ciclo(sqs, s3, conn, cola: str, bucket: str, catalogo) -> int:
    r = sqs.receive_message(QueueUrl=cola, MaxNumberOfMessages=5, WaitTimeSeconds=ESPERA,
                            VisibilityTimeout=VISIBILIDAD, AttributeNames=["ApproximateReceiveCount"])
    procesados = 0
    for m in r.get("Messages", []):
        intento = int(m["Attributes"].get("ApproximateReceiveCount", 1))
        try:
            cuerpo = json.loads(m["Body"])
        except json.JSONDecodeError:
            log.error("mensaje ilegible, se deja para la DLQ: %s", m["Body"][:200])
            continue
        try:
            res = procesar(cuerpo, s3, conn, bucket, catalogo)
            sqs.delete_message(QueueUrl=cola, ReceiptHandle=m["ReceiptHandle"])
            procesados += 1
            log.info("carga %s procesada: %s", cuerpo.get("carga_id"), res)
        except Exception as e:  # noqa: BLE001 - cualquier falla se reintenta y termina en la DLQ
            conn.rollback()
            log.exception("falló la carga %s (intento %s)", cuerpo.get("carga_id"), intento)
            try:
                db.marcar(conn, cuerpo["carga_id"], "error", intentos=intento, error=f"{type(e).__name__}: {e}"[:1000])
            except Exception:  # noqa: BLE001
                conn.rollback()
            # Reintento más pronto que el tiempo de visibilidad completo, con espera creciente
            espera = min(15 * 2 ** (intento - 1), VISIBILIDAD)
            try:
                sqs.change_message_visibility(QueueUrl=cola, ReceiptHandle=m["ReceiptHandle"], VisibilityTimeout=espera)
            except ClientError:
                pass
    return procesados


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    bucket, cola = os.environ["BUCKET"], os.environ["QUEUE_URL"]
    s3, sqs = boto3.client("s3"), boto3.client("sqs")
    conn = db.conectar()
    catalogo = cargar_catalogo()

    def parar(*_):
        global _detener
        _detener = True
    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    log.info("worker escuchando %s", cola)
    while not _detener:
        try:
            ciclo(sqs, s3, conn, cola, bucket, catalogo)
        except psycopg2_errors() as e:
            log.error("se perdió la base de datos (%s); reconectando", e)
            time.sleep(5)
            conn = db.conectar()
        except ClientError as e:
            log.error("error de AWS: %s", e)
            time.sleep(5)


def psycopg2_errors():
    import psycopg2
    return (psycopg2.OperationalError, psycopg2.InterfaceError)


if __name__ == "__main__":
    main()
