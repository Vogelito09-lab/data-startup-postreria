"""Worker de limpieza como función Lambda (E3).

La función se dispara con la cola SQS (event source mapping). Lambda entrega lotes de hasta
10 mensajes; cada uno se procesa con el mismo `procesar()` del worker de E2. Si un mensaje
falla, se reporta en `batchItemFailures` y solo ese vuelve a la cola: los demás del lote no se
repiten. Después de 3 intentos SQS lo manda a la DLQ, igual que antes.

Variables de entorno: BUCKET, DATABASE_URL (en E4 pasa a Secrets Manager).
"""
from __future__ import annotations

import json
import logging
import os

import boto3

import db
from limpieza import cargar_catalogo
from worker import procesar

log = logging.getLogger()
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Lo que vive fuera del handler se reutiliza entre invocaciones del mismo contenedor
# (arranque en frío solo la primera vez).
_s3 = boto3.client("s3")
_catalogo = cargar_catalogo()
_conn = None


def _conexion():
    global _conn
    if _conn is None or _conn.closed:
        _conn = db.conectar()
    return _conn


def handler(event, context):
    bucket = os.environ["BUCKET"]
    fallidos = []
    for record in event.get("Records", []):
        mid = record["messageId"]
        try:
            cuerpo = json.loads(record["body"])
            conn = _conexion()
            resumen = procesar(cuerpo, _s3, conn, bucket, _catalogo)
            log.info(json.dumps({"carga": cuerpo.get("carga_id"), "resultado": "procesada", **resumen}, default=str))
        except Exception as e:  # noqa: BLE001
            log.exception("falló el mensaje %s", mid)
            intento = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))
            try:
                if _conn is not None and not _conn.closed:
                    _conn.rollback()
                    if isinstance(cuerpo, dict) and "carga_id" in cuerpo:
                        db.marcar(_conn, cuerpo["carga_id"], "error", intentos=intento,
                                  error=f"{type(e).__name__}: {e}"[:1000])
            except Exception:  # noqa: BLE001
                pass
            fallidos.append({"itemIdentifier": mid})
    return {"batchItemFailures": fallidos}
