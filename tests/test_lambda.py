"""Prueba de la función Lambda con S3 emulado (moto) y un PostgreSQL de prueba.

    TEST_DATABASE_URL=postgresql://postgres@localhost:5433/salome_test python -m pytest tests/test_lambda.py
"""
import json
import os
import sys
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="define TEST_DATABASE_URL para correr esta prueba")
sys.path.insert(0, str(RAIZ / "services" / "worker"))


@pytest.fixture()
def entorno(monkeypatch):
    import psycopg2
    from moto import mock_aws
    with psycopg2.connect(URL) as c, c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS lineas_pedido, pedidos, clientes, cargas, productos CASCADE")
        cur.execute((RAIZ / "infra/sql/esquema.sql").read_text())
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("BUCKET", "bucket-prueba")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    for v in ("AWS_ENDPOINT_URL", "AWS_PROFILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    with mock_aws():
        import boto3
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="bucket-prueba", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
        sys.modules.pop("lambda_handler", None)
        import lambda_handler
        yield s3, lambda_handler


def mensaje(carga, key):
    return {"messageId": str(uuid.uuid4()), "body": json.dumps({"carga_id": carga, "key": key}),
            "attributes": {"ApproximateReceiveCount": "1"}}


def test_lote_con_un_mensaje_malo(entorno):
    s3, lh = entorno
    s3.put_object(Bucket="bucket-prueba", Key="raw/pedidos/fecha_carga=2026-11-12/a.csv",
                  Body=(RAIZ / "data/sample/semana_2026-10-25.csv").read_bytes())
    bueno = mensaje(str(uuid.uuid4()), "raw/pedidos/fecha_carga=2026-11-12/a.csv")
    malo = mensaje(str(uuid.uuid4()), "raw/pedidos/no-existe.csv")
    r = lh.handler({"Records": [bueno, malo]}, None)
    assert r == {"batchItemFailures": [{"itemIdentifier": malo["messageId"]}]}
    import psycopg2
    with psycopg2.connect(URL) as c, c.cursor() as cur:
        cur.execute("SELECT estado FROM cargas ORDER BY estado")
        assert [x[0] for x in cur.fetchall()] == ["error", "procesada"]
        cur.execute("SELECT count(*) FROM lineas_pedido")
        assert cur.fetchone()[0] > 0
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket="bucket-prueba", Prefix="clean/")["Contents"]]
    assert "clean/pedidos/pedidos_salome_clean.csv" in keys
