"""Calculos del tablero: KPIs, series y hallazgos.

Separado de app.py para poder probarlo sin Streamlit y para que los titulos
de las graficas se calculen de los datos (si cambian los datos, cambian los
hallazgos).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
QUINCENA = (15, 16, 30, 31, 1)
ID = "pedido_id"
MIN_DIAS_FFT = 42


def money(x: float) -> str:
    return f"${x:,.0f}"


def tickets(df: pd.DataFrame) -> pd.DataFrame:
    """Un renglon por pedido (o ticket)."""
    return df.groupby(ID).agg(fecha=("fecha", "first"), hora=("hora", "first"),
                                       total=("total", "sum"), canal=("canal", "first"))


def diario(df: pd.DataFrame) -> pd.DataFrame:
    t = tickets(df)
    d = t.groupby("fecha").agg(ventas=("total", "sum"), tickets=("total", "size"))
    d = d.asfreq("D", fill_value=0)
    d["ticket_prom"] = d["ventas"] / d["tickets"].replace(0, np.nan)
    d["media_7d"] = d["ventas"].rolling(7, min_periods=1).mean()
    d["quincena"] = d.index.day.isin(QUINCENA)
    return d


def kpis(df: pd.DataFrame) -> dict:
    t = tickets(df)
    fin = df["fecha"].max()
    ult = t[t["fecha"] > fin - pd.Timedelta(days=7)]["total"].sum()
    prev = t[(t["fecha"] <= fin - pd.Timedelta(days=7)) & (t["fecha"] > fin - pd.Timedelta(days=14))]["total"].sum()
    por_prod = df.groupby("producto")["total"].sum().sort_values(ascending=False)
    return {
        "ventas": t["total"].sum(),
        "ticket_prom": t["total"].mean(),
        "n_tickets": len(t),
        "estrella": por_prod.index[0],
        "estrella_pct": por_prod.iloc[0] / por_prod.sum() * 100,
        "semana": ult,
        "variacion": (ult / prev - 1) * 100 if prev else np.nan,
    }


def tendencia(d: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    m = d["ventas"].resample("MS").sum()
    m = m[m.index + pd.offsets.MonthEnd(0) <= d.index.max()]  # solo meses completos
    if len(m) >= 13:
        a, b = m.iloc[-1], m.iloc[-13]
        nombre = f"{MESES[m.index[-1].month - 1]} {m.index[-1].year}"
        titulo = (f"Las ventas crecen: {nombre} vendió {(a / b - 1) * 100:.0f}% más que el mismo mes del año anterior")
    else:
        titulo = "Tendencia de ventas diarias"
    return d, titulo


def histograma(df: pd.DataFrame) -> tuple[pd.Series, int, str]:
    t = tickets(df)["total"]
    bins = int(np.ceil(np.log2(len(t)) + 1))  # regla de Sturges
    med = t.median()
    p90 = t.quantile(0.9)
    titulo = f"La mitad de los pedidos es de {money(med)} o menos; 1 de cada 10 pasa de {money(p90)} (pasteles enteros)"
    return t, bins, titulo


def mapa_calor(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    t = tickets(df)
    t["dia"] = t["fecha"].dt.dayofweek
    n_sem = t["fecha"].dt.to_period("W").nunique()
    tabla = t.pivot_table(index="dia", columns="hora", values="total", aggfunc="sum", fill_value=0) / n_sem
    tabla.index = [DIAS[i].capitalize() for i in tabla.index]
    dia, hora = np.unravel_index(np.argmax(tabla.values), tabla.shape)
    titulo = (f"Los pedidos llegan sobre todo de noche: el pico es el {tabla.index[dia].lower()} de "
              f"{tabla.columns[hora]} a {tabla.columns[hora] + 1} h ({money(tabla.values.max())} por semana en esa hora)")
    return tabla, titulo


def dispersion(d: pd.DataFrame) -> tuple[pd.DataFrame, float, float, str]:
    x = d[d["tickets"] > 0]
    if len(x) < 7:
        return x, float("nan"), float("nan"), "Elige al menos una semana para ver la relación entre pedidos y venta"
    r = x["tickets"].corr(x["ventas"])
    pendiente, intercepto = np.polyfit(x["tickets"], x["ventas"], 1)
    titulo = (f"Cada pedido extra deja {money(pendiente)}: la venta depende de cuántos mensajes se convierten "
              f"en pedido (r = {r:.2f})")
    return x, pendiente, intercepto, titulo


def espectro(d: pd.DataFrame) -> tuple[pd.DataFrame, dict, str]:
    """FFT de las ventas diarias sin tendencia (se resta la media movil de 28 dias)."""
    s = d["ventas"].astype(float)
    if len(s) < MIN_DIAS_FFT:  # con pocas semanas no se pueden distinguir ciclos de 7 y 15 dias
        info = {"semanal": None, "quincena": None, "efecto_quincena": _efecto_quincena(d)}
        return pd.DataFrame(columns=["periodo", "potencia"]), info, (
            f"Para buscar ciclos elige un periodo de al menos {MIN_DIAS_FFT // 7} semanas")
    x = (s - s.rolling(28, center=True, min_periods=1).mean()).values
    frec = np.fft.rfftfreq(len(x), d=1)[1:]
    pot = (np.abs(np.fft.rfft(x)) ** 2)[1:]
    esp = pd.DataFrame({"periodo": 1 / frec, "potencia": pot / pot.max()})
    esp = esp[esp["periodo"].between(2, 40)]

    def pico(lo, hi):
        v = esp[esp["periodo"].between(lo, hi)]
        return v.loc[v["potencia"].idxmax()] if len(v) else None

    semanal, quinc = pico(6.5, 7.5), pico(13.5, 16.5)
    efecto_q = _efecto_quincena(d)
    info = {"semanal": semanal, "quincena": quinc, "efecto_quincena": efecto_q}
    partes = ["Las ventas laten cada 7 días"]
    if quinc is not None:
        partes.append(f" y cada ~{quinc['periodo']:.0f} días (quincena)")
    titulo = "".join(partes)
    if not np.isnan(efecto_q):
        titulo += f": en días de quincena se vende {efecto_q:.0f}% {'más' if efecto_q >= 0 else 'menos'}"
    return esp, info, titulo


def _efecto_quincena(d: pd.DataFrame) -> float:
    q, n = d.loc[d["quincena"], "ventas"], d.loc[~d["quincena"], "ventas"]
    if q.empty or n.empty or n.mean() == 0:
        return float("nan")
    return (q.mean() / n.mean() - 1) * 100


def productos_mes(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    g = df.copy()
    g["mes"] = g["fecha"].dt.to_period("M").dt.to_timestamp()
    tabla = g.pivot_table(index="mes", columns="categoria", values="total", aggfunc="sum", fill_value=0)
    # La categoria con el pico de temporada mas marcado (mes calendario vs. su promedio)
    por_mes = g.pivot_table(index=g["fecha"].dt.month, columns="categoria", values="total", aggfunc="sum")
    por_mes = por_mes / g.groupby(g["fecha"].dt.month)["fecha"].nunique().values[:, None]  # por dia
    ratio = por_mes.max() / por_mes.mean()
    cat = ratio.idxmax()
    mes = MESES[por_mes[cat].idxmax() - 1]
    nombre_mes = {"ene": "enero", "feb": "febrero", "mar": "marzo", "abr": "abril", "may": "mayo", "jun": "junio",
                  "jul": "julio", "ago": "agosto", "sep": "septiembre", "oct": "octubre", "nov": "noviembre",
                  "dic": "diciembre"}[mes]
    titulo = (f"{cat} se disparan en {nombre_mes}: venden {ratio[cat]:.1f} veces su promedio diario del año")
    return tabla, titulo


def dias_semana(d: pd.DataFrame) -> pd.Series:
    s = d.groupby(d.index.dayofweek)["ventas"].mean()
    s.index = [DIAS[i] for i in s.index]
    return s


def recomendaciones(df: pd.DataFrame, d: pd.DataFrame, info: dict, tabla_calor: pd.DataFrame) -> list[str]:
    sem = dias_semana(d)
    alto, bajo = sem.idxmax(), sem.idxmin()
    t = tickets(df)
    por_prod = df.groupby("producto")["total"].sum().sort_values(ascending=False)
    top2 = " y ".join(p.split(" (")[0].lower() for p in por_prod.index[:2])
    horas = tabla_calor.sum()
    pico = horas.idxmax()
    pct_noche = horas[horas.index >= 19].sum() / horas.sum() * 100
    return [
        f"**Prepara según el día, no igual toda la semana.** El {alto} se vende {sem[alto] / sem[bajo]:.1f} veces lo del "
        f"{bajo}. Como el cheesecake necesita reposar, decide la producción del fin de semana desde el jueves: "
        f"menos merma entre semana y menos pedidos rechazados el sábado.",
        (f"**Aprovecha la quincena.** Esos días se vende {info['efecto_quincena']:.0f}% más. "
         if info["efecto_quincena"] > 0 else "**Aprovecha la quincena.** ") + f"Ten base lista de "
        f"{top2} para los días 15-16 y 30-1, y publica ahí tus promociones en Instagram.",
        f"**Contesta rápido de noche.** El {pct_noche:.0f}% de las ventas entra por mensajes de 19 h en adelante "
        f"y el pico es a las {pico} h. Publica historias antes de esa hora y deja respuestas rápidas con menú y "
        f"precios en WhatsApp: un mensaje que tarda en contestarse es un pedido que se va a otra postrería.",
    ]
