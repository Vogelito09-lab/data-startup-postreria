"""Limpieza de los pedidos de Salomé.

Copia de services/worker/limpieza.py del repositorio del proyecto. Aquí el catálogo de
precios se lee de la carpeta datos/.

Es el mismo código que se usó a mano en E1; desde E2 lo ejecuta el worker cada vez
que llega un archivo nuevo a raw/. La función principal es `limpiar(df, catalogo)`,
que regresa el DataFrame limpio y un reporte con cuántos renglones se tocaron por
cada tipo de error (duplicados, formato, tipo de dato, faltantes, errores lógicos y
atípicos).

Las reglas no adivinan: cuando un valor se puede reconstruir con otra columna del
mismo renglón (por ejemplo unidades = total / precio) se reconstruye; cuando no, el
renglón se aparta como irrecuperable y se reporta.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REFERENCIA = Path(__file__).parent / "datos"
COLUMNAS = ["pedido_id", "cliente_id", "fecha_pedido", "hora_pedido", "fecha_entrega", "producto",
            "categoria", "unidades", "precio_unitario", "total", "canal", "entrega", "metodo_pago"]
CANALES = {"whatsapp": "WhatsApp", "wa": "WhatsApp", "whats": "WhatsApp",
           "instagram": "Instagram", "ig": "Instagram", "insta": "Instagram",
           "facebook": "Facebook", "fb": "Facebook", "face": "Facebook"}
ENTREGAS = {"domicilio": "Domicilio", "recoge": "Recoge", "recoger": "Recoge"}
PAGOS = {"efectivo": "Efectivo", "transferencia": "Transferencia", "tarjeta": "Tarjeta"}
NUMEROS = {"uno": 1, "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
# Máximo creíble por renglón para una persona que hornea sola (con margen).
MAXIMO_UNIDADES = {"Pasteles enteros": 3, "Temporada": 4, "Rebanadas": 12,
                   "Galletas y brownies": 5, "Eventos": 10}
ALIAS = {  # abreviaturas que la similitud de texto sola no resuelve bien
    "cheesecake entero": "Cheesecake frutos rojos entero",
    "pay limon": "Pay de limón entero",
    "brownies 6pz": "Caja de brownies (6 pz)",
    "rosca": "Rosca de Reyes",
    "pan de muerto": "Pan de muerto (4 pz)",
    "flan napolitano": "Flan napolitano entero",
    "cupcakes": "Cupcakes (docena)",
}


@dataclass
class Reporte:
    crudos: int = 0
    limpios: int = 0
    conteos: dict = field(default_factory=dict)
    irrecuperables: list = field(default_factory=list)

    def sumar(self, clave: str, n: int) -> None:
        self.conteos[clave] = self.conteos.get(clave, 0) + int(n)

    def como_dict(self) -> dict:
        return {"crudos": self.crudos, "limpios": self.limpios, "conteos": self.conteos,
                "irrecuperables": len(self.irrecuperables)}


def cargar_catalogo(ruta: Path | str = REFERENCIA / "catalogo_precios.csv") -> pd.DataFrame:
    cat = pd.read_csv(ruta, parse_dates=["vigente_desde"])
    return cat.sort_values("vigente_desde").reset_index(drop=True)


def _sin_acentos(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c))


def _clave(texto) -> str:
    t = _sin_acentos(str(texto)).lower().strip()
    t = t.replace("3 leches", "tres leches").replace("reb.", "rebanada").replace("reb ", "rebanada ")
    t = t.replace("cheescake", "cheesecake")
    return re.sub(r"\s+", " ", t)


def normalizar_producto(valor, oficiales: list[str]) -> str | None:
    if pd.isna(valor):
        return None
    if valor in oficiales:
        return valor
    clave = _clave(valor)
    por_clave = {_clave(o): o for o in oficiales}
    if clave in por_clave:
        return por_clave[clave]
    if clave in ALIAS:
        return ALIAS[clave]
    cerca = difflib.get_close_matches(clave, list(por_clave), n=1, cutoff=0.72)
    return por_clave[cerca[0]] if cerca else None


def a_numero(valor):
    """'2 pz' -> 2, 'dos' -> 2, '1 entero' -> 1, 3.0 -> 3. Lo demás queda NaN."""
    if pd.isna(valor):
        return np.nan
    if isinstance(valor, (int, float, np.integer, np.floating)):
        return float(valor)
    t = _clave(valor)
    m = re.match(r"^(-?\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))
    return float(NUMEROS[t.split()[0]]) if t and t.split()[0] in NUMEROS else np.nan


def a_fecha(serie: pd.Series) -> tuple[pd.Series, int]:
    """Acepta AAAA-MM-DD y DD/MM/AAAA. Regresa las fechas y cuántas venían en otro formato."""
    s = serie.astype("string").str.strip()
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    otro_formato = int((iso.isna() & dmy.notna()).sum())
    return iso.fillna(dmy).astype("datetime64[ns]"), otro_formato


def precio_catalogo(df: pd.DataFrame, catalogo: pd.DataFrame) -> pd.Series:
    """Precio de lista vigente en la fecha del pedido para cada renglón."""
    base = df[["producto", "fecha_pedido"]].reset_index()
    base = base.dropna(subset=["producto", "fecha_pedido"]).sort_values("fecha_pedido")
    base["fecha_pedido"] = base["fecha_pedido"].astype("datetime64[ns]")
    base["producto"] = base["producto"].astype(str)
    cat = catalogo[["producto", "vigente_desde", "precio"]].copy()
    cat["producto"] = cat["producto"].astype(str)
    cat["vigente_desde"] = cat["vigente_desde"].astype("datetime64[ns]")
    unido = pd.merge_asof(base, cat,
                          left_on="fecha_pedido", right_on="vigente_desde", by="producto",
                          direction="backward")
    return unido.set_index("index")["precio"].reindex(df.index)


def limpiar(crudo: pd.DataFrame, catalogo: pd.DataFrame | None = None) -> tuple[pd.DataFrame, Reporte]:
    catalogo = cargar_catalogo() if catalogo is None else catalogo
    oficiales = sorted(catalogo["producto"].unique())
    categorias = catalogo.drop_duplicates("producto").set_index("producto")["categoria"]
    rep = Reporte(crudos=len(crudo))
    faltan = [c for c in COLUMNAS if c not in crudo.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el archivo: {faltan}")
    df = crudo[COLUMNAS].copy()

    # 1. Duplicados exactos (el mismo renglón copiado dos veces del chat)
    dup = df.duplicated(keep="first")
    rep.sumar("duplicados", dup.sum())
    df = df[~dup].reset_index(drop=True)

    # 2. Formato: nombres de producto y canal escritos de distintas maneras
    nuevo = df["producto"].map(lambda v: normalizar_producto(v, oficiales))
    rep.sumar("formato_producto", (nuevo.notna() & (nuevo != df["producto"])).sum())
    df["producto"] = nuevo
    for col, mapa, clave in (("canal", CANALES, "formato_canal"), ("entrega", ENTREGAS, "formato_entrega"),
                             ("metodo_pago", PAGOS, "formato_pago")):
        limpio = df[col].map(lambda v: mapa.get(_clave(v)) if pd.notna(v) else None)
        rep.sumar(clave, (limpio.notna() & (limpio != df[col])).sum())
        df[col] = limpio
    # Nombre irreconocible: si la categoría y el precio de lista apuntan a un solo producto, es ese
    for i in df.index[df["producto"].isna()]:
        fecha, _ = a_fecha(pd.Series([df.at[i, "fecha_pedido"]]))
        precio_txt = pd.to_numeric(pd.Series([df.at[i, "precio_unitario"]]), errors="coerce").iloc[0]
        if pd.isna(fecha.iloc[0]) or pd.isna(precio_txt):
            continue
        vig = catalogo[(catalogo["vigente_desde"] <= fecha.iloc[0]) & (catalogo["categoria"] == df.at[i, "categoria"])]
        vig = vig.sort_values("vigente_desde").groupby("producto").tail(1)
        opciones = vig.loc[np.isclose(vig["precio"], precio_txt), "producto"].unique()
        if len(opciones) == 1:
            df.at[i, "producto"] = opciones[0]
            rep.sumar("producto_por_precio_y_categoria", 1)
    df["categoria"] = df["producto"].map(categorias)

    # 3. Tipos de dato: unidades escritas como texto y fechas en otro formato
    num = df["unidades"].map(a_numero)
    era_texto = df["unidades"].map(lambda v: isinstance(v, str) and not re.fullmatch(r"-?\d+(\.0+)?", v.strip()))
    rep.sumar("unidades_texto", (era_texto & num.notna()).sum())
    df["unidades"] = num
    df["pedido_id"] = pd.to_numeric(df["pedido_id"], errors="coerce")
    df["precio_unitario"] = pd.to_numeric(df["precio_unitario"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df["fecha_pedido"], n1 = a_fecha(df["fecha_pedido"])
    df["fecha_entrega"], n2 = a_fecha(df["fecha_entrega"])
    rep.sumar("fecha_formato", n1 + n2)
    hora = pd.to_datetime(df["hora_pedido"].astype("string"), format="%H:%M", errors="coerce")
    df["hora_pedido"] = hora.dt.strftime("%H:%M")

    # 4. Faltantes
    lista = precio_catalogo(df, catalogo)
    sin_precio = df["precio_unitario"].isna() & lista.notna()
    rep.sumar("precio_vacio", sin_precio.sum())
    df.loc[sin_precio, "precio_unitario"] = lista[sin_precio]

    def desde_total(mask):
        u = df.loc[mask, "total"] / df.loc[mask, "precio_unitario"]
        return u.where(np.isclose(u, u.round()) & (u > 0)).round()

    sin_u = df["unidades"].isna()
    rep.sumar("unidades_vacias", sin_u.sum())
    df.loc[sin_u, "unidades"] = desde_total(sin_u)
    rep.sumar("hora_vacia_sin_imputar", df["hora_pedido"].isna().sum())

    # 5. Errores lógicos
    neg = df["unidades"] < 0
    rep.sumar("unidades_negativas", neg.sum())
    df.loc[neg, "unidades"] = df.loc[neg, "unidades"].abs()

    invertidas = df["fecha_entrega"] < df["fecha_pedido"]
    rep.sumar("fechas_invertidas", invertidas.sum())
    for i in df.index[invertidas]:
        fp, fe = df.at[i, "fecha_pedido"], df.at[i, "fecha_entrega"]
        corregida = fe + pd.DateOffset(years=1)
        if 0 <= (corregida - fp).days <= 14:      # año viejo tecleado en enero
            df.at[i, "fecha_entrega"] = corregida
        else:                                      # columnas al revés
            df.at[i, "fecha_pedido"], df.at[i, "fecha_entrega"] = fe, fp

    # 6. Atípicos imposibles (un cero de más): se reconstruyen con total / precio
    tope = df["categoria"].map(MAXIMO_UNIDADES)
    atip = df["unidades"] > tope
    rep.sumar("unidades_atipicas", atip.sum())
    df.loc[atip, "unidades"] = desde_total(atip)

    # 5b. Total que no cuadra con unidades x precio
    calc = df["unidades"] * df["precio_unitario"]
    mal = df["total"].notna() & calc.notna() & ~np.isclose(df["total"], calc)
    rep.sumar("total_inconsistente", mal.sum())
    sin_total = df["total"].isna() & calc.notna()
    rep.sumar("total_vacio", sin_total.sum())
    df.loc[mal | sin_total, "total"] = calc[mal | sin_total]

    # Precio que no es el de lista: se reporta, no se cambia (pudo ser un descuento)
    distinto = df["precio_unitario"].notna() & lista.notna() & ~np.isclose(df["precio_unitario"], lista)
    rep.sumar("precio_distinto_a_lista_reportado", distinto.sum())

    # Irrecuperables: sin producto reconocible, sin fecha o sin forma de saber unidades
    criticas = ["pedido_id", "producto", "fecha_pedido", "fecha_entrega", "unidades", "precio_unitario", "total"]
    malos = df[criticas].isna().any(axis=1)
    rep.irrecuperables = df[malos].to_dict("records")
    rep.sumar("irrecuperables_apartados", malos.sum())
    df = df[~malos].copy()

    # Mismo pedido y producto en dos renglones tras normalizar nombres: se conserva el primero
    clave = df.duplicated(["pedido_id", "producto"], keep="first")
    rep.sumar("duplicados_tras_normalizar", clave.sum())
    df = df[~clave]

    df = df.astype({"pedido_id": "int64", "unidades": "int64"})
    df["precio_unitario"] = df["precio_unitario"].round(2)
    df["total"] = df["total"].round(2)
    df = df.sort_values(["fecha_pedido", "pedido_id", "producto"]).reset_index(drop=True)
    rep.limpios = len(df)
    return df, rep


def validar_limpio(df: pd.DataFrame) -> list[str]:
    """Reglas que todo archivo de clean/ debe cumplir. Lista vacía = todo bien."""
    problemas = []
    if df.duplicated().any():
        problemas.append("hay duplicados")
    if df[["producto", "fecha_pedido", "fecha_entrega", "unidades", "precio_unitario", "total"]].isna().any().any():
        problemas.append("hay faltantes en columnas críticas")
    if (df["unidades"] <= 0).any():
        problemas.append("hay unidades no positivas")
    if not np.allclose(df["total"], df["unidades"] * df["precio_unitario"]):
        problemas.append("total distinto de unidades x precio")
    if (pd.to_datetime(df["fecha_entrega"]) < pd.to_datetime(df["fecha_pedido"])).any():
        problemas.append("entrega antes del pedido")
    if (df["unidades"] > df["categoria"].map(MAXIMO_UNIDADES)).any():
        problemas.append("unidades por encima del máximo creíble")
    return problemas


if __name__ == "__main__":
    import json
    import sys

    entrada = sys.argv[1] if len(sys.argv) > 1 else "data/historial/pedidos_salome_2020_2026.csv"
    salida = sys.argv[2] if len(sys.argv) > 2 else "data/historial/pedidos_salome_clean.csv"
    limpio, reporte = limpiar(pd.read_csv(entrada, dtype=str))
    limpio.to_csv(salida, index=False, date_format="%Y-%m-%d")
    print(json.dumps(reporte.como_dict(), indent=2, ensure_ascii=False))
    print("validación:", validar_limpio(limpio) or "ok")
