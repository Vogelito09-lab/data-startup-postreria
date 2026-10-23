"""Generador de pedidos sinteticos para Salome (postreria sin tienda fisica).

Todos los pedidos llegan por Instagram o WhatsApp y se entregan a domicilio
o se recogen. Simula del 1-abr-2025 al 30-sep-2026 (18 meses) con:
  tendencia de crecimiento, ciclo semanal, efecto quincena, horas en que
  llegan los mensajes, 14 de febrero, 10 de mayo, graduaciones (jun-jul),
  Dia de Muertos y diciembre.
Siembra errores a proposito: faltantes, negativos, atipicos, nombres mal
escritos, tipos de dato sucios y duplicados. La columna total no se
recalcula, asi que tambien hay inconsistencias logicas.

Es un sustituto mientras se consiguen los pedidos reales: productos, precios
y volumenes son supuestos que se ajustan con la entrevista.

Uso: python scripts/generar_ventas.py  -> data/raw/pedidos_salome.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
dias = pd.date_range("2025-04-01", "2026-09-30", freq="D")

# producto: (categoria, precio MXN, peso relativo en un pedido, media de unidades extra)
productos = {
    "Cheesecake clásico (rebanada)": ("Rebanadas", 75, 20, 1.3),
    "Pastel de tres leches (rebanada)": ("Rebanadas", 65, 16, 1.2),
    "Brownie": ("Galletas y brownies", 45, 10, 1.5),
    "Galleta con chispas": ("Galletas y brownies", 35, 9, 3.0),
    "Cheesecake entero": ("Pasteles enteros", 520, 6, 0.0),
    "Pastel de temporada": ("Pasteles enteros", 550, 3, 0.0),
}
nombres = list(productos)
semana = np.array([0.75, 0.70, 0.80, 0.95, 1.20, 1.45, 1.15])  # lun..dom
horas = np.arange(9, 24)
peso_hora = np.array([1, 2, 3, 4, 5, 4, 3, 3, 4, 5, 7, 9, 10, 8, 4], dtype=float)
peso_hora /= peso_hora.sum()

filas = []
pedido = 5000
for dia in dias:
    t = (dia - dias[0]).days
    m, d = dia.month, dia.day
    factor = (1 + 0.0007 * t) * semana[dia.weekday()]
    if d in (15, 16, 30, 31, 1):
        factor *= 1.25                      # quincena
    if m == 2 and 12 <= d <= 14:
        factor *= 2.0                       # San Valentin
    if m == 5 and 8 <= d <= 10:
        factor *= 2.6                       # Dia de las Madres
    if m in (6, 7):
        factor *= 1.10                      # graduaciones
    if m == 12 and d >= 15:
        factor *= 1.40
    if m == 1 and d <= 10:
        factor *= 0.80                      # cuesta de enero

    pesos = np.array([productos[p][2] for p in nombres], dtype=float)
    if (m == 5 and 8 <= d <= 10) or (m == 2 and 12 <= d <= 14) or m == 12 or m in (6, 7):
        pesos[nombres.index("Cheesecake entero")] *= 2.5      # fechas de regalo y fiesta
        pesos[nombres.index("Pastel de temporada")] *= 2.5
    if (m == 10 and d >= 20) or (m == 11 and d <= 2) or m == 12:
        pesos[nombres.index("Pastel de temporada")] *= 2.0    # sabores de temporada
    pesos /= pesos.sum()

    for _ in range(rng.poisson(24 * factor)):
        pedido += 1
        hora = rng.choice(horas, p=peso_hora)
        canal = rng.choice(["WhatsApp", "Instagram"], p=[0.58, 0.42])
        entrega = rng.choice(["Domicilio", "Recoger"], p=[0.65, 0.35])
        pago = rng.choice(["Transferencia", "Efectivo"], p=[0.70, 0.30])
        n_items = 1 + rng.poisson(0.45)
        for i in rng.choice(len(nombres), size=min(n_items, len(nombres)), replace=False, p=pesos):
            prod = nombres[i]
            cat, precio, _, extra = productos[prod]
            unidades = 1 + rng.poisson(extra)
            filas.append([pedido, dia.date(), f"{hora:02d}:{rng.integers(0, 60):02d}", prod, cat,
                          unidades, precio, unidades * precio, canal, entrega, pago])

df = pd.DataFrame(filas, columns=["pedido_id", "fecha", "hora", "producto", "categoria", "unidades",
                                  "precio_unitario", "total", "canal", "entrega", "metodo_pago"])
df["unidades"] = df["unidades"].astype("object")

# ---- Errores sembrados para practicar preprocesamiento ----
n = len(df)
df.loc[rng.choice(n, 40, replace=False), "unidades"] = np.nan              # faltantes
df.loc[rng.choice(n, 20, replace=False), "precio_unitario"] = np.nan       # faltantes
neg = rng.choice(n, 15, replace=False)
df.loc[neg, "unidades"] = -df.loc[neg, "unidades"].astype(float)           # errores logicos
df.loc[rng.choice(n, 10, replace=False), "unidades"] = 999                 # atipicos
idx = rng.choice(n, 30, replace=False)
df.loc[idx, "producto"] = df.loc[idx, "producto"].str.lower()              # formato
idx = rng.choice(n, 15, replace=False)
df.loc[idx, "producto"] = df.loc[idx, "producto"] + "  "                   # espacios extra
idx = rng.choice(n, 12, replace=False)
df.loc[idx, "unidades"] = df.loc[idx, "unidades"].astype(str) + " pz"      # tipo de dato
idx = rng.choice(n, 20, replace=False)
df.loc[idx, "total"] = df.loc[idx, "total"] * 10                           # total inconsistente
df = pd.concat([df, df.sample(30, random_state=1)])                        # duplicados
df = df.sample(frac=1, random_state=2).reset_index(drop=True)

salida = Path(__file__).resolve().parents[1] / "data" / "raw" / "pedidos_salome.csv"
salida.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(salida, index=False)
print(f"{len(df):,} registros ({df['pedido_id'].nunique():,} pedidos) de {dias[0].date()} a {dias[-1].date()}")
