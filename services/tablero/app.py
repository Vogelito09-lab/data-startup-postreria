"""Tablero empresarial de Salome, postreria por pedido (E1).

Lee los datos limpios de la zona clean/ del bucket S3. Las credenciales
NUNCA van en el codigo: boto3 las toma de variables de entorno, de
~/.aws/credentials o de .streamlit/secrets.toml (que esta en .gitignore).

Correr:  streamlit run services/tablero/app.py
Modo local solo para desarrollo:  DATA_SOURCE=local streamlit run services/tablero/app.py
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import importlib

import analisis as an

an = importlib.reload(an)  # toma siempre la versión más reciente de analisis.py

AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#9a9893"
CATEGORIAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]

st.set_page_config(page_title="Tablero · Salomé", page_icon="🍰", layout="wide")


def _secreto(seccion: str, clave: str, defecto=None):
    try:
        return st.secrets[seccion][clave]
    except Exception:
        return defecto


@st.cache_data(ttl=600, show_spinner="Leyendo pedidos de la nube…")
def cargar() -> tuple[pd.DataFrame, str]:
    fuente = os.getenv("DATA_SOURCE") or _secreto("datos", "fuente", "s3")
    if fuente == "local":
        ruta = Path(__file__).resolve().parents[2] / "data" / "clean" / "pedidos_salome_clean.csv"
        return pd.read_csv(ruta, parse_dates=["fecha"]), f"archivo local ({ruta.name}) · modo desarrollo"

    import boto3

    bucket = os.getenv("S3_BUCKET") or _secreto("s3", "bucket")
    llave = os.getenv("S3_KEY") or _secreto("s3", "key", "clean/pedidos/pedidos_salome_clean.csv")
    region = os.getenv("AWS_DEFAULT_REGION") or _secreto("s3", "region", "us-east-1")
    if not bucket:
        st.error("Falta el nombre del bucket. Configúralo en .streamlit/secrets.toml (sección [s3]) "
                 "o en la variable de entorno S3_BUCKET.")
        st.stop()
    cred = {}
    if _secreto("aws", "aws_access_key_id"):
        cred = {"aws_access_key_id": _secreto("aws", "aws_access_key_id"),
                "aws_secret_access_key": _secreto("aws", "aws_secret_access_key")}
    s3 = boto3.client("s3", region_name=region, **cred)
    cuerpo = s3.get_object(Bucket=bucket, Key=llave)["Body"].read()
    return pd.read_csv(io.BytesIO(cuerpo), parse_dates=["fecha"]), f"s3://{bucket}/{llave}"


def estilo(fig: go.Figure, alto: int = 340) -> go.Figure:
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=10, b=10), hovermode="closest",
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=-0.2, title=None))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def titulo(texto: str, pregunta: str):
    st.markdown("#### " + texto.replace("$", "\\$"))
    st.caption(pregunta)


datos, origen = cargar()

# ---------- Filtros ----------
st.title("🍰 Salomé · tablero de pedidos")
st.caption("Pedidos por Instagram y WhatsApp, a domicilio o para recoger")
with st.sidebar:
    st.header("Filtros")
    ini, fin = datos["fecha"].min().date(), datos["fecha"].max().date()
    rango = st.date_input("Periodo", value=(ini, fin), min_value=ini, max_value=fin)
    cats = sorted(datos["categoria"].unique())
    elegidas = st.multiselect("Categorías", cats, default=cats)
    st.caption(f"Fuente: {origen}")

if isinstance(rango, tuple) and len(rango) == 2:
    df = datos[(datos["fecha"].dt.date >= rango[0]) & (datos["fecha"].dt.date <= rango[1])]
else:
    df = datos
df = df[df["categoria"].isin(elegidas)]
# El color sigue a la categoría (fijo por ventas totales), no a su posición tras filtrar
COLOR_CAT = {c: CATEGORIAS[i] for i, c in
             enumerate(datos.groupby("categoria")["total"].sum().sort_values(ascending=False).index)}
if df.empty:
    st.warning("No hay ventas con esos filtros.")
    st.stop()

d = an.diario(df)
k = an.kpis(df)

# ---------- KPIs ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ventas del periodo", an.money(k["ventas"]), f"{k['n_tickets']:,} pedidos", delta_color="off")
c2.metric("Ticket promedio por pedido", an.money(k["ticket_prom"]))
estrella = k["estrella"].split(" (")[0].replace("Pastel ", "").capitalize()
c3.markdown(f"<div style='font-size:0.875rem'>Producto estrella</div>"
            f"<div style='font-size:1.75rem;line-height:1.25;padding:4px 0'>{estrella}</div>", unsafe_allow_html=True)
c3.caption(f"{k['estrella_pct']:.0f}% de las ventas")
c4.metric("Últimos 7 días", an.money(k["semana"]), f"{k['variacion']:+.1f}% vs. semana anterior")
st.divider()

# ---------- 1. Líneas: tendencia ----------
serie, t1 = an.tendencia(d)
titulo(t1, "¿Mi negocio está creciendo?")
fig = go.Figure()
fig.add_scatter(x=serie.index, y=serie["ventas"], name="Venta diaria", mode="lines",
                line=dict(color=AZUL, width=1), opacity=0.35, hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>")
fig.add_scatter(x=serie.index, y=serie["media_7d"], name="Promedio de 7 días", mode="lines",
                line=dict(color=AZUL, width=2.5), hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>")
fig.update_yaxes(tickprefix="$", title="Ventas por día")
st.plotly_chart(estilo(fig, 360), width="stretch")

col_a, col_b = st.columns(2)

# ---------- 2. Histograma: ticket ----------
with col_a:
    tk, bins, t2 = an.histograma(df)
    titulo(t2, f"¿Cuánto gasta un cliente por pedido? · {bins} intervalos (regla de Sturges)")
    tope = tk.quantile(0.99)
    fig = px.histogram(tk[tk <= tope], nbins=bins, color_discrete_sequence=[AZUL])
    fig.add_vline(x=tk.median(), line_dash="dash", line_color=NARANJA,
                  annotation_text=f"Mediana {an.money(tk.median())}", annotation_position="top right")
    fig.update_traces(marker_line_width=1, marker_line_color="white", hovertemplate="$%{x}<br>%{y:,} pedidos<extra></extra>")
    fig.update_layout(showlegend=False, bargap=0.02)
    fig.update_xaxes(tickprefix="$", title="Total del pedido (sin el 1% más alto)")
    fig.update_yaxes(title="Pedidos")
    st.plotly_chart(estilo(fig), width="stretch")

# ---------- 3. Mapa de calor: día x hora ----------
with col_b:
    tabla, t3 = an.mapa_calor(df)
    titulo(t3, "¿Qué días y a qué horas llegan los pedidos? · venta promedio por semana según la hora del mensaje")
    fig = px.imshow(tabla, color_continuous_scale=["#f3f7fd", "#9cc3f0", AZUL, "#0d3f80"], aspect="auto",
                    labels=dict(x="Hora", y="", color="Venta"))
    fig.update_traces(hovertemplate="%{y} %{x}:00 h<br>$%{z:,.0f} por semana<extra></extra>", xgap=2, ygap=2)
    fig.update_xaxes(dtick=1, ticksuffix="h")
    st.plotly_chart(estilo(fig), width="stretch")

col_c, col_d = st.columns(2)

# ---------- 4. Dispersión: clientes vs venta ----------
with col_c:
    x, m, b, t4 = an.dispersion(d)
    titulo(t4, "¿Vendo más por tener más pedidos o porque cada uno es más grande? · cada punto es un día")
    x = x.assign(tipo=x["quincena"].map({True: "Día de quincena", False: "Día normal"}))
    fig = px.scatter(x, x="tickets", y="ventas", color="tipo", opacity=0.7,
                     category_orders={"tipo": ["Día normal", "Día de quincena"]},
                     color_discrete_map={"Día normal": AZUL, "Día de quincena": NARANJA},
                     custom_data=[x.index.strftime("%d %b %Y")])
    fig.update_traces(marker=dict(size=8, line=dict(width=1, color="white")),
                      hovertemplate="%{customdata[0]}<br>%{x} pedidos · $%{y:,.0f}<extra></extra>")
    xs = [x["tickets"].min(), x["tickets"].max()]
    if not np.isnan(m):
        fig.add_scatter(x=xs, y=[m * v + b for v in xs], mode="lines", name="Tendencia",
                        line=dict(color=GRIS, width=2, dash="dash"), hoverinfo="skip")
    fig.update_xaxes(title="Pedidos en el día")
    fig.update_yaxes(tickprefix="$", title="Venta del día")
    st.plotly_chart(estilo(fig), width="stretch")

# ---------- 5. Análisis espectral (FFT) ----------
with col_d:
    esp, info, t5 = an.espectro(d)
    titulo(t5, "¿Mis ventas siguen ciclos? · FFT de la venta diaria sin tendencia; periodo = 1/frecuencia")
    fig = go.Figure()
    if esp.empty:
        st.info("Con menos de 6 semanas no hay suficientes datos para el análisis espectral. "
                "Amplía el periodo en la barra lateral.")
    fig.add_scatter(x=esp["periodo"], y=esp["potencia"], mode="lines", line=dict(color=AZUL, width=2),
                    name="Potencia", hovertemplate="Ciclo de %{x:.1f} días<br>potencia %{y:.2f}<extra></extra>")
    for nombre, p in (("Semanal", info["semanal"]), ("Quincena", info["quincena"])):
        if p is not None:
            fig.add_annotation(x=p["periodo"], y=np.log10(p["potencia"]), text=f"{nombre}: {p['periodo']:.1f} días",
                               showarrow=True, arrowhead=0, ax=40, ay=-30)
    fig.update_xaxes(title="Periodo del ciclo (días)", dtick=2)
    fig.update_yaxes(title="Potencia relativa", type="log")
    fig.update_layout(showlegend=False)
    if not esp.empty:
        st.plotly_chart(estilo(fig), width="stretch")

# ---------- 6. Barras apiladas: categorías por mes ----------
tabla_m, t6 = an.productos_mes(df)
titulo(t6, "¿Qué vendo en cada temporada? · ventas mensuales por categoría")
largo = tabla_m.reset_index().melt(id_vars="mes", var_name="Categoría", value_name="Ventas")
orden = list(tabla_m.sum().sort_values(ascending=False).index)
fig = px.bar(largo, x="mes", y="Ventas", color="Categoría", category_orders={"Categoría": orden},
             color_discrete_map=COLOR_CAT)
fig.update_traces(marker_line_width=1, marker_line_color="white",
                  hovertemplate="%{x|%b %Y}<br>%{fullData.name}: $%{y:,.0f}<extra></extra>")
fig.update_layout(bargap=0.15)
fig.update_yaxes(tickprefix="$", title="Ventas del mes")
fig.update_xaxes(title=None, dtick="M2", tickformat="%b %y")
st.plotly_chart(estilo(fig, 380), width="stretch")

# ---------- Recomendaciones ----------
st.divider()
st.subheader("Tres recomendaciones para el negocio")
for i, r in enumerate(an.recomendaciones(df, d, info, tabla), 1):
    st.markdown(f"{i}. " + r.replace("$", "\\$"))

with st.expander("Ver los datos diarios"):
    st.dataframe(d[["ventas", "tickets", "ticket_prom"]].rename(columns={"tickets": "pedidos"}).round(0), width="stretch")
