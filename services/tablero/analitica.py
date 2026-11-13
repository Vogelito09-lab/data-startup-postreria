"""Cálculos que comparten el tablero, los notebooks y las figuras de los documentos.

Todo trabaja sobre el CSV limpio (una fila por producto dentro de cada pedido). La
venta se cuenta en la fecha de entrega, que es el día en que Salomé produce.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"])
    df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"])
    df["hora"] = pd.to_datetime(df["hora_pedido"], format="%H:%M", errors="coerce").dt.hour
    return df


def pesos(x: float) -> str:
    return f"${x:,.0f}"


def es_quincena(fechas: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    f = pd.DatetimeIndex(fechas)
    ultimo = f.days_in_month
    return np.isin(f.day, [1, 14, 15, 16]) | (f.day >= ultimo - 1)


ESPECIALES = {(2, 13), (2, 14), (4, 30), (5, 8), (5, 9), (5, 10), (12, 23), (12, 24), (12, 30), (12, 31),
              (1, 2), (1, 3), (1, 4), (1, 5), (1, 6)}


def es_fecha_especial(fechas) -> np.ndarray:
    """San Valentín, 10 de mayo, Navidad, Año Nuevo, Reyes y Día del Padre (con sus vísperas)."""
    f = pd.DatetimeIndex(fechas)
    md = np.array([(m, d) in ESPECIALES for m, d in zip(f.month, f.day)])
    padre = (f.month == 6) & (f.dayofweek == 6) & (f.day >= 15) & (f.day <= 21)
    return md | padre


def cierres_registrados() -> pd.Series:
    from pathlib import Path
    ruta = Path(__file__).resolve().parent / "referencia" / "calendario_cierres.csv"
    return pd.read_csv(ruta)["fecha"] if ruta.exists() else pd.Series(dtype=str)


def abiertos(fechas, cierres=None) -> np.ndarray:
    """Días en que Salomé trabajó: martes a domingo, lunes solo en fechas especiales,
    sin el 25 de diciembre, el 1 de enero ni su calendario de cierres. Un día abierto sin
    pedidos cuenta como venta cero (demanda real), uno cerrado no cuenta."""
    f = pd.DatetimeIndex(fechas)
    cierres = cierres_registrados() if cierres is None else cierres
    ok = (f.dayofweek != 0) | es_fecha_especial(f)
    ok &= ~(((f.month == 12) & (f.day == 25)) | ((f.month == 1) & (f.day == 1)))
    return ok & ~f.isin(pd.to_datetime(cierres))


def serie_diaria(df: pd.DataFrame, columna: str = "total") -> pd.Series:
    """Venta (o unidades) por día de entrega, con 0 en los días sin entregas."""
    s = df.groupby("fecha_entrega")[columna].sum()
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(idx, fill_value=0).astype(float)


def pedidos_por_pedido(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("pedido_id").agg(total=("total", "sum"), fecha_entrega=("fecha_entrega", "first"),
                                       fecha_pedido=("fecha_pedido", "first"), hora=("hora", "first"),
                                       canal=("canal", "first"), lineas=("producto", "size"))


def kpis(df: pd.DataFrame) -> dict:
    ped = pedidos_por_pedido(df)
    fin = df["fecha_entrega"].max()
    ult = df[df["fecha_entrega"] > fin - pd.Timedelta(days=7)]["total"].sum()
    ant = df[(df["fecha_entrega"] <= fin - pd.Timedelta(days=7)) & (df["fecha_entrega"] > fin - pd.Timedelta(days=14))]["total"].sum()
    por_prod = df.groupby("producto")["total"].sum().sort_values(ascending=False)
    return {
        "ventas": df["total"].sum(), "pedidos": len(ped),
        "ticket": ped["total"].mean(), "ticket_mediana": ped["total"].median(),
        "estrella": por_prod.index[0], "estrella_pct": por_prod.iloc[0] / por_prod.sum(),
        "ult7": ult, "ant7": ant, "var7": (ult / ant - 1) if ant else np.nan, "fin": fin,
    }


def por_dia_semana(df: pd.DataFrame) -> pd.Series:
    """Venta promedio por día de la semana en los días que abrió (con o sin pedidos)."""
    s = serie_diaria(df)
    s = s[abiertos(s.index)]
    return s.groupby(s.index.dayofweek).mean().reindex(range(7))


def efecto_quincena(df: pd.DataFrame) -> float:
    return prueba_quincena(df)["efecto"]


def prueba_quincena(df: pd.DataFrame, desde: str = "2022-01-01") -> dict:
    """Quincena contra días normales, ya descontado el día de la semana de cada año y sin fechas
    especiales (prueba t de Welch sobre la venta relativa)."""
    from scipy import stats
    s = serie_diaria(df)
    s = s[abiertos(s.index) & ~es_fecha_especial(s.index) & (s.index >= desde)]
    rel = s / s.groupby([s.index.year, s.index.dayofweek]).transform("mean")
    q = es_quincena(s.index)
    t, p = stats.ttest_ind(rel[q], rel[~q], equal_var=False)
    return {"efecto": float(rel[q].mean() / rel[~q].mean() - 1), "p_valor": float(p),
            "dias_quincena": int(q.sum()), "dias_normales": int((~q).sum())}


def espectro(serie: pd.Series, ventana: int = 28) -> pd.DataFrame:
    """Periodograma de la serie diaria sin tendencia. Regresa periodo (días) y potencia."""
    x = serie - serie.rolling(ventana, center=True, min_periods=1).mean()
    x = x.to_numpy() - x.mean()
    f = np.fft.rfftfreq(len(x), d=1.0)
    p = np.abs(np.fft.rfft(x)) ** 2 / len(x)
    out = pd.DataFrame({"frecuencia": f[1:], "periodo": 1 / f[1:], "potencia": p[1:]})
    return out


def picos(esp: pd.DataFrame, rango=(2.05, 60), n: int = 5, separacion: float = 0.06) -> pd.DataFrame:
    """Picos locales más fuertes, sin repetir vecinos de la misma frecuencia."""
    e = esp[(esp.periodo >= rango[0]) & (esp.periodo <= rango[1])].sort_values("potencia", ascending=False)
    elegidos = []
    for _, r in e.iterrows():
        if all(abs(np.log(r.periodo / x.periodo)) > separacion for x in elegidos):
            elegidos.append(r)
        if len(elegidos) == n:
            break
    out = pd.DataFrame(elegidos).reset_index(drop=True)
    out["potencia_relativa"] = out["potencia"] / out["potencia"].iloc[0]
    return out


def potencia_cerca(esp: pd.DataFrame, periodo: float, tolerancia: float = 0.04) -> float:
    m = (esp.periodo / periodo - 1).abs() <= tolerancia
    return float(esp.loc[m, "potencia"].max()) if m.any() else 0.0


def mapa_dia_hora(df: pd.DataFrame) -> pd.DataFrame:
    """Pedidos recibidos por día de la semana y hora del mensaje."""
    ped = pedidos_por_pedido(df).dropna(subset=["hora"])
    ped["dia"] = ped["fecha_pedido"].dt.dayofweek
    tabla = ped.pivot_table(index="dia", columns="hora", values="total", aggfunc="size", fill_value=0)
    return tabla.reindex(index=range(7), fill_value=0)


def mensual(df: pd.DataFrame) -> pd.Series:
    return df.groupby(df["fecha_entrega"].dt.to_period("M"))["total"].sum()


def titulos(df: pd.DataFrame, completo: pd.DataFrame | None = None) -> dict:
    """Cada gráfica lleva su hallazgo como título; se recalculan con los datos que haya.
    `completo` es la historia entera: sirve para comparar contra el año anterior y para medir
    la quincena aunque el filtro solo muestre unos meses."""
    completo = df if completo is None else completo
    k = kpis(df)
    t = {}
    m = mensual(df)
    # solo meses completos: el primero y el último del filtro pueden venir a medias
    f0, f1 = df["fecha_entrega"].min(), df["fecha_entrega"].max()
    if f0.day != 1:
        m = m.iloc[1:]
    if f1.day != f1.days_in_month:
        m = m.iloc[:-1]
    anios = df["fecha_entrega"].dt.year
    completos = sorted(a for a in anios.unique() if ((anios == a) & (df["fecha_entrega"].dt.month == 12)).any())
    ultimo = m.index[-1] if len(m) else None
    hace_un_anio = ultimo - 12 if len(m) else None
    mc = mensual(completo)
    if len(m) and hace_un_anio in mc.index:
        cambio = m[ultimo] / mc[hace_un_anio] - 1
        anios_llenos = mc.groupby(mc.index.year).size()
        mc_llenos = mc[mc.index.year.isin(anios_llenos[anios_llenos == 12].index)]
        top = (mc_llenos.groupby(mc_llenos.index.year).apply(lambda x: list(x.nlargest(3).index.month)).explode().value_counts())
        fuertes = [MESES[i - 1] for i in top.index[:3]]
        t["lineas"] = (f"{MESES[ultimo.month - 1].capitalize()} {ultimo.year} vendió {abs(cambio):.0%} "
                       f"{'más' if cambio >= 0 else 'menos'} que un año antes; los picos de cada año caen en "
                       f"{fuertes[0]}, {fuertes[1]} y {fuertes[2]}")
    elif len(m):
        t["lineas"] = (f"La venta mensual fue de {pesos(m.min())} a {pesos(m.max())}; "
                       f"el mejor mes fue {MESES[m.idxmax().month - 1]} de {m.idxmax().year}")
    else:
        t["lineas"] = "Venta por mes"
    if len(completos) >= 2:
        a, b = completos[-2], completos[-1]
        va, vb = df[anios == a]["total"].sum(), df[anios == b]["total"].sum()
        ua, ub = df[anios == a]["unidades"].sum(), df[anios == b]["unidades"].sum()
        cp, cu = vb / va - 1, ub / ua - 1
        if cu < 0.02:
            if cp >= 0:
                remate = "en volumen el negocio ya no crece; lo que sube es el precio"
            elif cp > cu:
                remate = "vendió un poco menos y las alzas de precio casi lo compensaron"
            else:
                remate = "el volumen dejó de crecer"
        else:
            remate = "sigue creciendo en piezas, no solo en precio"
        t["lineas_sub"] = f"{b} cerró {cp:+.0%} en pesos y {cu:+.0%} en piezas contra {a}: {remate}"
    ped = pedidos_por_pedido(df)
    p90 = ped["total"].quantile(.9)
    t["histograma"] = (f"La mitad de los pedidos es de {pesos(ped.total.median())} o menos; "
                       f"1 de cada 10 pasa de {pesos(p90)}, casi siempre por un pastel entero")
    mh = mapa_dia_hora(df)
    tarde = mh.loc[:, [h for h in mh.columns if h >= 19]].to_numpy().sum() / mh.to_numpy().sum()
    d, h = np.unravel_index(np.argmax(mh.to_numpy()), mh.shape)
    t["calor"] = (f"{tarde:.0%} de los pedidos llega después de las 7 de la noche; "
                  f"el pico es el {DIAS[d]} de {int(mh.columns[h])} a {int(mh.columns[h]) + 1} h")
    dia = df.groupby("fecha_entrega").agg(pedidos=("pedido_id", "nunique"), venta=("total", "sum"))
    pend = np.polyfit(dia.pedidos, dia.venta, 1)[0]
    r = np.corrcoef(dia.pedidos, dia.venta)[0, 1]
    t["dispersion"] = (f"Cada pedido extra en un día deja {pesos(pend)} más (r = {r:.2f}): "
                       f"la venta depende de cuántos pedidos entran, no de pedidos más grandes")
    esp = espectro(serie_diaria(df))
    pk = picos(esp)
    q = efecto_quincena(completo)
    pq = potencia_cerca(esp, 15.2) / pk.potencia.iloc[0]
    pqq = prueba_quincena(completo)
    t["espectro"] = (f"El ciclo fuerte es de {pk.periodo.iloc[0]:.1f} días (la semana); la quincena no aparece como pico "
                     f"({pq:.0%} de la potencia semanal)"
                     + (f" y vale {q:+.0%} en venta" if pqq["p_valor"] < 0.05 else " ni se distingue del azar en venta"))
    cat = df.assign(mes=df.fecha_entrega.dt.month).groupby(["mes", "categoria"])["total"].sum().unstack(fill_value=0)
    dias_mes = df.assign(mes=df.fecha_entrega.dt.month).groupby("mes")["fecha_entrega"].nunique()
    enteros_dia = cat["Pasteles enteros"] / dias_mes
    t["barras"] = (f"Los pasteles enteros mandan todo el año; en {MESES[enteros_dia.idxmax() - 1]} venden "
                   f"{enteros_dia.max() / enteros_dia.mean():.1f} veces su promedio diario")
    dsem = por_dia_semana(df)
    t["dia_semana"] = (f"El sábado vende {dsem[5] / dsem[1]:.1f} veces lo del martes "
                       f"({pesos(dsem[5])} contra {pesos(dsem[1])}); el lunes no hay entregas")
    t["kpi"] = k
    return t


def recomendaciones(df: pd.DataFrame, ultimos_dias: int = 365) -> list[dict]:
    """Tres recomendaciones para Salomé, calculadas con el último año de pedidos."""
    fin = df["fecha_entrega"].max()
    u = df[df["fecha_entrega"] > fin - pd.Timedelta(days=ultimos_dias)]
    ent = u[u["categoria"].isin(["Pasteles enteros", "Eventos"])]
    diarios = ent.groupby("fecha_entrega")["unidades"].sum()
    tope = int(diarios.max()) if len(diarios) else 0
    s = serie_diaria(u)
    sabados = s.index[(s.index.dayofweek == 5) & abiertos(s.index)]
    llenos = int((diarios.reindex(sabados, fill_value=0) >= tope).sum()) if tope else 0
    sab_ent = ent[ent["fecha_entrega"].dt.dayofweek == 5]
    anticipo = (sab_ent["fecha_entrega"] - sab_ent["fecha_pedido"]).dt.days
    con_jueves = float((sab_ent["unidades"] * (anticipo >= 2)).sum() / max(sab_ent["unidades"].sum(), 1))
    dsem = por_dia_semana(df)
    q = prueba_quincena(df)
    ped = pedidos_por_pedido(u).dropna(subset=["hora"])
    noche = float((ped["hora"] >= 19).mean())
    sin_venta = float((s[abiertos(s.index) & (s.index.dayofweek.isin([1, 2]))] == 0).mean())
    if q["p_valor"] < 0.05:
        quinc = f"En quincena vendes {q['efecto']:.0%} más que un día igual de la semana, así que ese es buen momento para promociones. "
    else:
        quinc = ("La quincena no mueve tus ventas de forma clara (la diferencia que se ve es chica y puede ser casualidad), "
                 "así que no cambies la producción por ella. ")
    return [
        {"titulo": "Arma el fin de semana desde el jueves",
         "texto": (f"El sábado vendes {dsem[5] / dsem[1]:.1f} veces lo de un martes, y para el jueves ya tienes apartados "
                   f"{con_jueves:.0%} de los pasteles enteros del sábado. Esa noche puedes dejar listos los cheesecakes "
                   f"que necesitan reposar y comprar el queso crema justo. Entre semana no hornees de más: en "
                   f"{sin_venta:.0%} de los martes y miércoles que abriste no hubo ninguna entrega.")},
        {"titulo": "Los sábados fuertes ya llegan a tu tope: aparta con anticipo",
         "texto": (f"En {llenos} de {len(sabados)} sábados del último año entregaste {tope} pasteles enteros, que es lo más que "
                   f"sale de tu cocina en un día normal. Esos días seguramente le dijiste que no a alguien. Abre la agenda del sábado "
                   f"el miércoles en tus historias y, cuando se llene, ofrece entrega el domingo.")},
        {"titulo": "Contesta rápido de noche",
         "texto": (f"{noche:.0%} de los pedidos llega después de las 7 de la noche. Publica el menú en historias por la tarde "
                   f"y deja respuestas rápidas en WhatsApp con precios para contestar al momento. " + quinc).strip()},
    ]
