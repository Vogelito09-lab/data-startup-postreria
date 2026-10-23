"""Sube los datos al data lake en S3 respetando la convencion de nombres.

  raw/pedidos/fecha_carga=AAAA-MM-DD/pedidos_salome.csv   (tal como llegaron, nunca se modifican)
  clean/pedidos/pedidos_salome_clean.csv                  (version vigente que lee el tablero)
  clean/pedidos/reporte_limpieza.json                       (que se corrigio)

Las credenciales salen de `aws configure` (~/.aws/credentials), nunca del codigo.

Uso: python scripts/subir_s3.py <nombre-del-bucket>
"""
import sys
from datetime import date
from pathlib import Path

import boto3

raiz = Path(__file__).resolve().parents[1]
bucket = sys.argv[1] if len(sys.argv) > 1 else None
if not bucket:
    sys.exit("Uso: python scripts/subir_s3.py <nombre-del-bucket>")

s3 = boto3.client("s3")
archivos = {
    raiz / "data/raw/pedidos_salome.csv": f"raw/pedidos/fecha_carga={date.today()}/pedidos_salome.csv",
    raiz / "data/clean/pedidos_salome_clean.csv": "clean/pedidos/pedidos_salome_clean.csv",
    raiz / "data/clean/reporte_limpieza.json": "clean/pedidos/reporte_limpieza.json",
}
for local, llave in archivos.items():
    s3.upload_file(str(local), bucket, llave)
    print(f"OK  {local.name}  ->  s3://{bucket}/{llave}")
