"""De dónde lee el tablero. Se elige con la variable FUENTE:

  postgres  vista v_lineas de RDS (E2 en adelante, la opción del servidor)
  s3        clean/pedidos/pedidos_salome_clean.csv del data lake (como en E1)
  local     un CSV en disco, solo para desarrollo (RUTA_LOCAL)

Ninguna credencial vive en el código: S3 usa el rol del servidor y PostgreSQL toma
DATABASE_URL de /etc/salome/tablero.env.
"""
from __future__ import annotations

import io
import os

import pandas as pd

BUCKET = os.getenv("BUCKET", "data-startup-salome-13454721")
LLAVE = "clean/pedidos/pedidos_salome_clean.csv"


def fuente() -> str:
    return os.getenv("FUENTE", "s3")


def describir() -> str:
    f = fuente()
    if f == "postgres":
        return "PostgreSQL · vista v_lineas"
    if f == "s3":
        return f"s3://{BUCKET}/{LLAVE}"
    from pathlib import Path
    return f"archivo local {Path(os.getenv('RUTA_LOCAL', 'pedidos_salome_clean.csv')).name}"


def leer_pedidos() -> pd.DataFrame:
    f = fuente()
    if f == "postgres":
        import psycopg2
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
            return pd.read_sql("SELECT * FROM v_lineas ORDER BY fecha_pedido, pedido_id", conn)
    if f == "s3":
        import boto3
        cuerpo = boto3.client("s3").get_object(Bucket=BUCKET, Key=LLAVE)["Body"].read()
        return pd.read_csv(io.BytesIO(cuerpo))
    return pd.read_csv(os.getenv("RUTA_LOCAL", "data/historial/pedidos_salome_clean.csv"))


def leer_cargas(n: int = 8) -> pd.DataFrame | None:
    if fuente() != "postgres":
        return None
    import psycopg2
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        return pd.read_sql("""SELECT recibida_en, estado, registros_crudos, registros_limpios,
                                     round(extract(epoch FROM procesada_en - recibida_en)::numeric, 1) AS segundos
                              FROM cargas ORDER BY recibida_en DESC LIMIT %s""", conn, params=(n,))


def ruta_referencia(nombre: str):
    from pathlib import Path
    return Path(__file__).resolve().parent / "referencia" / nombre


def leer_cierres() -> pd.Series:
    ruta = ruta_referencia("calendario_cierres.csv")
    return pd.read_csv(ruta)["fecha"] if ruta.exists() else pd.Series(dtype=str)
