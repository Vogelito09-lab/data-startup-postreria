"""Parte el CSV crudo en dos archivos para la demostración en vivo de E2:
  historial: todo lo entregado antes del 25 de octubre de 2026
  semana:    los pedidos que se entregan del 25 al 31 de octubre (la "semana nueva" que se sube en vivo)
Los dos conservan los errores de captura, porque así llegan a raw/.
"""
import pandas as pd

ORIGEN = "data/historial/pedidos_salome_2020_2026.csv"
CORTE = "2026-10-25"

df = pd.read_csv(ORIGEN, dtype=str)
entrega = pd.to_datetime(df["fecha_entrega"], errors="coerce")
nuevos = df["pedido_id"].isin(df.loc[entrega >= CORTE, "pedido_id"])
df[~nuevos].to_csv("data/historial/historial_hasta_2026-10-24.csv", index=False)
df[nuevos].to_csv("data/sample/semana_2026-10-25.csv", index=False)
print(f"historial: {(~nuevos).sum():,} renglones · semana nueva: {nuevos.sum()} renglones")
