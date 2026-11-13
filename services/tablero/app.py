"""Tablero de Salomé (v3): lo que pasó, hacia dónde va la venta y el pronóstico de la API de modelos.

    FUENTE=local RUTA_LOCAL=data/historial/pedidos_salome_clean.csv streamlit run services/tablero/app.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import analitica as an
import fuente
import modelos_e2 as m2

st.set_page_config(page_title="Salomé · pedidos", page_icon="🍰", layout="wide")
CAFE, ROSA, CREMA, GRIS = "#7a4a2e", "#d97a8c", "#e9c46a", "#8d8d8d"
COLORES_CAT = {"Pasteles enteros": CAFE, "Rebanadas": ROSA, "Galletas y brownies": CREMA,
               "Eventos": "#6a9fb5", "Temporada": "#9b6fb0"}
st.markdown("""<style>
div[data-testid="stMetricValue"] {font-size: 1.7rem;}
h3 {margin-top: 0.6rem;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner="Leyendo pedidos...")
def cargar() -> pd.DataFrame:
    return an.preparar(fuente.leer_pedidos())


@st.cache_data(ttl=600, show_spinner="Ajustando la regresión...")
def modelos(df: pd.DataFrame):
    cierres = fuente.leer_cierres()
    res = m2.ajustar(df, cierres)
    stl = m2.descomposicion(df)
    return res, stl


def estilo(fig: go.Figure, alto: int = 340) -> go.Figure:
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.08, x=0), font=dict(size=13))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#eee")
    return fig


try:
    todo = cargar()
except Exception as e:  # noqa: BLE001
    st.error(f"No pude leer los pedidos de {fuente.describir()}: {e}")
    st.stop()

# ---------------- barra lateral
with st.sidebar:
    st.header("Filtros")
    fmin, fmax = todo.fecha_entrega.min().date(), todo.fecha_entrega.max().date()
    inicio_def = (pd.Timestamp(fmax) - pd.DateOffset(years=1)).to_period("M").to_timestamp() + pd.DateOffset(months=1)
    rango = st.date_input("Periodo (fecha de entrega)", value=(max(fmin, inicio_def.date()), fmax),
                          min_value=fmin, max_value=fmax)
    cats = st.multiselect("Categorías", sorted(todo.categoria.unique()), default=sorted(todo.categoria.unique()))
    st.caption(f"Datos: {fuente.describir()}")
    st.caption(f"{len(todo):,} renglones · {todo.pedido_id.nunique():,} pedidos · último pedido entregado el {fmax:%d/%m/%Y}")
    cargas = None
    try:
        cargas = fuente.leer_cargas()
    except Exception:  # noqa: BLE001
        pass
    if cargas is not None and len(cargas):
        st.subheader("Últimas cargas")
        c = cargas.copy()
        c["recibida_en"] = pd.to_datetime(c["recibida_en"]).dt.tz_convert("America/Mexico_City").dt.strftime("%d/%m %H:%M")
        st.dataframe(c, hide_index=True, width="stretch")
    if st.button("Actualizar ahora"):
        st.cache_data.clear()
        st.rerun()

ini, fin = (rango if isinstance(rango, tuple) and len(rango) == 2 else (fmin, fmax))
df = todo[(todo.fecha_entrega.dt.date >= ini) & (todo.fecha_entrega.dt.date <= fin) & todo.categoria.isin(cats)]
if df.empty:
    st.warning("No hay pedidos con esos filtros.")
    st.stop()

t = an.titulos(df, todo)
k = t["kpi"]
st.title("Salomé · tablero de pedidos")
st.caption(f"Del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}. La venta se cuenta el día de entrega, que es cuando horneas.")

# ---------------- KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ventas del periodo", an.pesos(k["ventas"]), f"{k['pedidos']:,} pedidos", delta_color="off", delta_arrow="off")
c2.metric("Ticket promedio", an.pesos(k["ticket"]), f"mediana {an.pesos(k['ticket_mediana'])}", delta_color="off", delta_arrow="off")
c3.metric("Producto estrella", k["estrella"].replace(" frutos rojos", ""), f"{k['estrella_pct']:.0%} de la venta", delta_color="off", delta_arrow="off")
c4.metric("Últimos 7 días", an.pesos(k["ult7"]), f"{k['var7']:+.0%} vs. 7 días anteriores" if pd.notna(k["var7"]) else "sin semana previa")

dsem = an.por_dia_semana(df)
mejor = int(dsem.idxmax())
q = an.prueba_quincena(todo)
frase_q = (f"en quincena vendes **{q['efecto']:+.0%}** que un día igual de la semana" if q["p_valor"] < 0.05
           else "la quincena **no cambia** tus ventas de forma clara")
st.info(f"En 30 segundos: tu mejor día es el **{an.DIAS[mejor]}** ({an.pesos(dsem[mejor])} en promedio), "
        f"lo que más dinero deja es el **{k['estrella'].lower()}** y {frase_q}.")

# ---------------- v3: pronóstico servido por la API de modelos
MODELOS_URL = os.getenv("MODELOS_URL", "").rstrip("/")


@st.cache_data(ttl=60, show_spinner=False)
def api(ruta: str, **params):
    import json
    import urllib.parse
    import urllib.request
    url = f"{MODELOS_URL}{ruta}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read())


if MODELOS_URL:  # sin API de modelos (E2 o desarrollo) la sección simplemente no aparece
    st.header("Lo que viene")
    try:
        pv, pe = api("/pronostico", dias=14), api("/pronostico", dias=14, serie="enteros")
        f = pd.DataFrame(pv["dias"])
        f["fecha"] = pd.to_datetime(f["fecha"])
        fe = pd.DataFrame(pe["dias"])
        semana_prox = f.head(7)[f.head(7).abierto].pronostico.sum()
        enteros_prox = fe.head(7)[fe.head(7).abierto].pronostico.sum()
        st.subheader(f"Los próximos 7 días apuntan a {an.pesos(semana_prox)} y unos {enteros_prox:.0f} pasteles enteros")
        hist = an.serie_diaria(todo).tail(28)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(f.fecha) + list(f.fecha[::-1]), y=list(f.superior) + list(f.inferior[::-1]),
                                 fill="toself", fillcolor="rgba(233,196,106,0.35)", line=dict(width=0), name="Banda de 95%",
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, mode="lines+markers", name="Últimas 4 semanas",
                                 line=dict(color=ROSA), marker=dict(size=4)))
        fig.add_trace(go.Scatter(x=f.fecha, y=f.pronostico, mode="lines+markers", name=f"Pronóstico ({pv['modelo']})",
                                 line=dict(color=CAFE, width=2.5)))
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(estilo(fig, 340), width="stretch")
        st.caption(f"Calculado por la API de modelos con datos hasta el {pv['datos_hasta']}. La banda es amplia porque con "
                   f"poco más de un pedido diario un solo pastel cambia el día; úsala como rango, no como número exacto.")
        st.markdown("**Pasteles enteros por día y aviso de día fuerte** (el aviso se decide dos días antes)")
        cols = st.columns(7)
        for col, (_, d) in zip(cols, fe.head(7).iterrows()):
            dia = pd.Timestamp(d["fecha"])
            titulo = f"{an.DIAS[dia.dayofweek][:3].capitalize()} {dia.day}"
            if not d["abierto"]:
                col.markdown(f"{titulo}<br><span style='font-size:1.4rem;color:#999'>descanso</span>", unsafe_allow_html=True)
                continue
            c = api("/clasificar", fecha=d["fecha"])
            aviso = ("<span style='color:#7a4a2e;font-weight:600'>día fuerte</span>" if c["dia_fuerte"]
                     else "<span style='color:#888'>normal</span>")
            col.markdown(f"{titulo}<br><span style='font-size:1.4rem'>{d['pronostico']:.1f}</span><br>{aviso} · "
                         f"{c['probabilidad']:.0%}", unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"La API de modelos no respondió ({e}). El resto del tablero sigue funcionando.")

# ---------------- 1 y 2
a, b = st.columns(2)
with a:
    st.subheader(t["lineas"])
    mes = an.mensual(df)
    mes.index = mes.index.to_timestamp()
    fig = go.Figure(go.Scatter(x=mes.index, y=mes.values, mode="lines+markers", line=dict(color=CAFE, width=2.5),
                               name="Venta mensual", hovertemplate="%{x|%b %Y}: $%{y:,.0f}<extra></extra>"))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(estilo(fig), width="stretch")
    if "lineas_sub" in t:
        st.caption(t["lineas_sub"])
with b:
    st.subheader(t["histograma"])
    ped = an.pedidos_por_pedido(df)
    bins = int(np.ceil(np.log2(len(ped)) + 1))  # regla de Sturges
    fig = px.histogram(ped, x="total", nbins=bins, color_discrete_sequence=[ROSA])
    fig.add_vline(ped.total.median(), line_dash="dash", line_color=CAFE, annotation_text="mediana")
    fig.update_xaxes(title="Total del pedido", tickprefix="$")
    fig.update_yaxes(title="Pedidos")
    st.plotly_chart(estilo(fig), width="stretch")
    st.caption(f"{bins} barras por la regla de Sturges (1 + log₂ {len(ped):,}). La cola larga a la derecha son los pasteles enteros y los pedidos de evento.")

# ---------------- 3 y 4
a, b = st.columns(2)
with a:
    st.subheader(t["calor"])
    mh = an.mapa_dia_hora(df)
    fig = go.Figure(go.Heatmap(z=mh.values, x=[f"{int(h)} h" for h in mh.columns], y=[d.capitalize() for d in an.DIAS],
                               colorscale=[[0, "#fff7f3"], [1, CAFE]], hovertemplate="%{y} %{x}: %{z} pedidos<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(estilo(fig), width="stretch")
    st.caption("Día y hora en que llegó el mensaje del pedido (no el día de entrega).")
with b:
    st.subheader(t["dispersion"])
    dia = df.groupby("fecha_entrega").agg(pedidos=("pedido_id", "nunique"), venta=("total", "sum")).reset_index()
    dia["tipo"] = np.where(an.es_fecha_especial(dia.fecha_entrega), "Fecha especial", "Día normal")
    fig = px.scatter(dia, x="pedidos", y="venta", color="tipo", opacity=.55,
                     color_discrete_map={"Día normal": ROSA, "Fecha especial": CAFE})
    p = np.polyfit(dia.pedidos, dia.venta, 1)
    xs = np.array([dia.pedidos.min(), dia.pedidos.max()])
    fig.add_trace(go.Scatter(x=xs, y=np.polyval(p, xs), mode="lines", line=dict(color=GRIS, dash="dash"), name="Ajuste lineal"))
    fig.update_xaxes(title="Pedidos entregados en el día")
    fig.update_yaxes(title="Venta del día", tickprefix="$")
    st.plotly_chart(estilo(fig), width="stretch")

# ---------------- 5 y 6
a, b = st.columns(2)
with a:
    st.subheader(t["espectro"])
    esp = an.espectro(an.serie_diaria(df))
    esp = esp[(esp.periodo >= 2) & (esp.periodo <= 35)]
    fig = go.Figure(go.Scatter(x=esp.periodo, y=esp.potencia, mode="lines", line=dict(color=CAFE),
                               hovertemplate="%{x:.1f} días<extra></extra>"))
    for per, txt in ((3.5, ""), (7, "semana"), (15.2, "quincena"), (30.4, "mes")):
        fig.add_vline(per, line_dash="dot", line_color=ROSA, annotation_text=txt, annotation_position="top right")
    fig.update_xaxes(title="Periodo (días) = 1 / frecuencia", range=[2, 35], tickvals=[2, 3.5, 7, 10, 15, 20, 25, 30])
    fig.update_yaxes(title="Potencia |X(f)|²", showticklabels=False)
    st.plotly_chart(estilo(fig), width="stretch")
    st.caption("FFT de la venta diaria sin tendencia (se le resta su media móvil de 28 días). Los picos de 3.5 y 2.3 días "
               "son armónicos de la semana: aparecen porque los lunes no hay entregas y el sábado sube de golpe.")
with b:
    st.subheader(t["barras"])
    cat = df.assign(mes=df.fecha_entrega.dt.month).groupby(["mes", "categoria"])["total"].sum().reset_index()
    dias_mes = df.assign(mes=df.fecha_entrega.dt.month).groupby("mes")["fecha_entrega"].nunique()
    cat["por_dia"] = cat["total"] / cat["mes"].map(dias_mes)
    cat["mes_nombre"] = cat["mes"].map(lambda i: an.MESES[i - 1][:3])
    fig = px.bar(cat, x="mes_nombre", y="por_dia", color="categoria", color_discrete_map=COLORES_CAT)
    fig.update_xaxes(title=None, categoryorder="array", categoryarray=[m[:3] for m in an.MESES])
    fig.update_yaxes(title="Venta promedio por día con entregas", tickprefix="$")
    st.plotly_chart(estilo(fig), width="stretch")

# ---------------- v2: serie de tiempo y regresión
st.divider()
st.header("Hacia dónde va la venta")
res, stl = modelos(todo)
mp = res["metricas_prueba"]
semana = an.serie_diaria(todo).resample("W-SUN").sum()
semana = semana[semana.index >= m2.INICIO_MODELO]
idx = pd.date_range(m2.INICIO_MODELO, todo.fecha_entrega.max(), freq="D")
abiertos = m2.dias_abiertos(pd.Series(0, index=idx), fuente.leer_cierres())
pred = m2.predecir(res, idx).where(abiertos, 0).clip(lower=0).resample("W-SUN").sum()
tend = m2.tendencia(res, idx).resample("W-SUN").mean() * 6   # semana típica de 6 días abiertos
pendiente = res["beta"]["t_anios"]
base = m2.tendencia(res, pd.DatetimeIndex([todo.fecha_entrega.max()])).iloc[0]
cat_p = pd.read_csv(fuente.ruta_referencia("catalogo_precios.csv"))
cat_p["anio"] = cat_p.vigente_desde.str[:4].astype(int)
alza = cat_p[cat_p.anio >= 2023].groupby(["producto", "anio"]).precio.last().unstack().pct_change(axis=1).stack().mean()
st.subheader(f"La tendencia sube {an.pesos(pendiente)} por año en un día típico ({pendiente / base:.0%} anual); "
             f"como tus precios suben cerca de {alza:.0%} al año, el volumen casi no crece")
fig = go.Figure()
fig.add_trace(go.Scatter(x=semana.index, y=semana.values, name="Venta real por semana", line=dict(color=ROSA, width=1.5)))
fig.add_trace(go.Scatter(x=pred.index, y=pred.values, name="Regresión (calendario + tendencia)", line=dict(color=CAFE, width=1.5)))
fig.add_trace(go.Scatter(x=tend.index, y=tend.values, name="Línea de tendencia", line=dict(color="black", width=3, dash="dash")))
fig.add_vrect(x0=pd.Timestamp(m2.CORTE_PRUEBA), x1=todo.fecha_entrega.max(), fillcolor="#efefef", opacity=0.6, layer="below", line_width=0,
              annotation_text="año de prueba", annotation_position="top left")
fig.update_yaxes(tickprefix="$", tickformat=",.0f")
st.plotly_chart(estilo(fig, 380), width="stretch")
st.caption(f"Regresión lineal por mínimos cuadrados (ecuación normal, hecha a mano) con tendencia lineal, día de la semana, "
           f"mes, quincena y fechas fuertes. En el año de prueba se equivoca en promedio {an.pesos(mp['MAE'])} por día "
           f"(R² = {mp['R2']:.2f}); repetir lo del mismo día de la semana pasada se equivoca {an.pesos(res['metricas_ingenuo_prueba']['MAE'])}.")

part = stl.seasonal.var() / stl.observed.var()
st.subheader(f"El ciclo semanal explica {part:.0%} de lo que sube y baja la venta diaria; casi todo lo demás es ruido del día")
desde = pd.Timestamp(fin) - pd.Timedelta(days=180)
comp = pd.DataFrame({"Venta observada": stl.observed, "Tendencia": stl.trend, "Estacionalidad semanal": stl.seasonal,
                     "Residuo": stl.resid})
comp = comp[comp.index >= max(desde, comp.index.min())]
fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=list(comp.columns))
for i, (col, color) in enumerate(zip(comp.columns, [ROSA, CAFE, CREMA, GRIS]), start=1):
    fig.add_trace(go.Scatter(x=comp.index, y=comp[col], line=dict(color=color, width=1.4), showlegend=False,
                             mode="lines" if col != "Residuo" else "markers", marker=dict(size=3)), row=i, col=1)
fig.update_yaxes(tickprefix="$", tickformat=",.0f")
st.plotly_chart(estilo(fig, 580).update_layout(margin=dict(t=30)), width="stretch")
st.caption("Descomposición STL (periodo 7) de la venta diaria, últimos 6 meses del periodo elegido.")

# ---------------- recomendaciones
st.divider()
st.header("Tres cosas que puedes hacer esta semana")
for col, r in zip(st.columns(3), an.recomendaciones(todo)):
    with col:
        st.markdown(f"**{r['titulo']}**")
        st.write(r["texto"])
