"""Limpieza de ventas de la postreria.

Modulo reutilizable: en E1 se corre a mano y en E2 lo llamara el worker.
Corrige los 5 tipos de error que pide la rubrica y cuenta cuantos
registros cambio en cada uno.

Uso: python services/worker/limpieza.py data/raw/pedidos_salome.csv data/clean
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LIMITE_UNIDADES = 30  # mas de 30 piezas en un pedido es imposible para este negocio


def _canonico(nombres: pd.Series) -> dict:
    """Mapea cada variante (minusculas, espacios) al nombre mas frecuente."""
    llave = nombres.str.strip().str.lower()
    mas_frecuente = nombres.str.strip().groupby(llave).agg(lambda s: s.value_counts().index[0])
    return {v: mas_frecuente[k] for v, k in zip(nombres, llave)}


def limpiar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rep: dict[str, int] = {"registros_entrada": len(df)}
    df = df.copy()

    # 1. Duplicados exactos
    antes = len(df)
    df = df.drop_duplicates()
    rep["duplicados_eliminados"] = antes - len(df)

    # 2. Formato: nombres de producto en minusculas o con espacios
    mapa = _canonico(df["producto"].astype(str))
    nuevo = df["producto"].map(mapa)
    rep["formato_producto_corregido"] = int((nuevo != df["producto"]).sum())
    df["producto"] = nuevo

    # 3. Tipos de dato: "2 pz" -> 2 ; fechas y horas a tipos reales
    texto = df["unidades"].astype(str).str.contains(r"[a-zA-Z]", regex=True) & df["unidades"].notna()
    rep["tipo_dato_corregido"] = int(texto.sum())
    df["unidades"] = pd.to_numeric(df["unidades"].astype(str).str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")
    df["fecha"] = pd.to_datetime(df["fecha"])
    for c in ("precio_unitario", "total"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 4. Faltantes en precio: se recupera del catalogo (precio mas comun del producto)
    catalogo = df.groupby("producto")["precio_unitario"].agg(lambda s: s.mode().iloc[0])
    falta_precio = df["precio_unitario"].isna()
    df.loc[falta_precio, "precio_unitario"] = df.loc[falta_precio, "producto"].map(catalogo)
    rep["faltantes_precio_imputados"] = int(falta_precio.sum())

    # Unidades que se pueden reconstruir con el total del ticket
    desde_total = (df["total"] / df["precio_unitario"]).round()
    reconstruible = desde_total.between(1, LIMITE_UNIDADES)

    falta_u = df["unidades"].isna()
    ok = falta_u & reconstruible
    df.loc[ok, "unidades"] = desde_total[ok]
    rep["faltantes_unidades_reconstruidos"] = int(ok.sum())

    # 5a. Errores logicos: unidades negativas o cero
    neg = df["unidades"] <= 0
    ok = neg & reconstruible
    df.loc[ok, "unidades"] = desde_total[ok]
    df.loc[neg & ~ok, "unidades"] = df.loc[neg & ~ok, "unidades"].abs()
    rep["unidades_negativas_corregidas"] = int(neg.sum())

    # 5b. Atipicos: unidades imposibles (999, > limite)
    atip = df["unidades"] > LIMITE_UNIDADES
    ok = atip & reconstruible
    df.loc[ok, "unidades"] = desde_total[ok]
    rep["atipicos_corregidos"] = int(ok.sum())

    # Lo que no se pudo recuperar se elimina (y se reporta)
    invalido = df["unidades"].isna() | (df["unidades"] <= 0) | (df["unidades"] > LIMITE_UNIDADES)
    rep["registros_eliminados_irrecuperables"] = int(invalido.sum())
    df = df[~invalido]

    # 5c. Error logico: total distinto de unidades x precio
    df["unidades"] = df["unidades"].astype(int)
    correcto = df["unidades"] * df["precio_unitario"]
    malo = ~np.isclose(df["total"], correcto)
    rep["totales_inconsistentes_recalculados"] = int(malo.sum())
    df["total"] = correcto

    df["hora"] = pd.to_datetime(df["hora"], format="%H:%M").dt.hour
    df = df.sort_values(["fecha", "pedido_id"]).reset_index(drop=True)
    rep["registros_salida"] = len(df)
    return df, rep


def reporte_md(rep: dict) -> str:
    filas = [
        ("Duplicados", "Filas idénticas repetidas", rep["duplicados_eliminados"], "Eliminadas"),
        ("Formato", "Nombre de producto en minúsculas o con espacios", rep["formato_producto_corregido"], "Unificado al nombre oficial"),
        ("Tipo de dato", "Unidades escritas como texto (\"2 pz\")", rep["tipo_dato_corregido"], "Convertidas a número"),
        ("Faltantes", "Precio unitario vacío", rep["faltantes_precio_imputados"], "Precio de catálogo del producto"),
        ("Faltantes", "Unidades vacías", rep["faltantes_unidades_reconstruidos"], "Reconstruidas con total ÷ precio"),
        ("Error lógico", "Unidades negativas", rep["unidades_negativas_corregidas"], "Reconstruidas con total ÷ precio"),
        ("Atípicos", "Unidades imposibles (999)", rep["atipicos_corregidos"], "Reconstruidas con total ÷ precio"),
        ("Error lógico", "Total ≠ unidades × precio", rep["totales_inconsistentes_recalculados"], "Total recalculado"),
        ("Irrecuperables", "Sin forma de reconstruir", rep["registros_eliminados_irrecuperables"], "Eliminados"),
    ]
    md = ["# Reporte de limpieza", "",
          f"Registros de entrada: **{rep['registros_entrada']:,}** · Registros limpios: **{rep['registros_salida']:,}**", "",
          "| Tipo de error | Qué se encontró | Registros | Corrección |", "|---|---|---:|---|"]
    md += [f"| {a} | {b} | {c:,} | {d} |" for a, b, c, d in filas]
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    entrada = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/pedidos_salome.csv")
    destino = Path(sys.argv[2] if len(sys.argv) > 2 else "data/clean")
    destino.mkdir(parents=True, exist_ok=True)
    limpio, reporte = limpiar(pd.read_csv(entrada))
    limpio.to_csv(destino / "pedidos_salome_clean.csv", index=False)
    (destino / "reporte_limpieza.json").write_text(json.dumps(reporte, indent=2))
    Path("docs").mkdir(exist_ok=True)
    Path("docs/reporte-limpieza.md").write_text(reporte_md(reporte), encoding="utf-8")
    print(json.dumps(reporte, indent=2))
