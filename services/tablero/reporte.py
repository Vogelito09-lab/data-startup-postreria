"""Reporte gerencial en PDF para la dueña de Salomé.

Usa los mismos cálculos del tablero (analisis.py), así que el PDF siempre
coincide con lo que se ve en pantalla para el periodo y las categorías
elegidas. Las gráficas se dibujan con matplotlib y el PDF se arma con
reportlab, sin dependencias externas al navegador.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#9a9893"
TINTA, SUAVE = "#1f2328", "#5b6169"
CATEGORIAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

ACC = colors.HexColor(AZUL)
INK = colors.HexColor(TINTA)
MUT = colors.HexColor(SUAVE)
FONDO = colors.HexColor("#EEF4FC")
LINEA = colors.HexColor("#d7dbe0")

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK)
SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, leading=13, textColor=MUT)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=ACC, spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=6)
B = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
PQ = ParagraphStyle("pq", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUT, spaceAfter=2)
LI = ParagraphStyle("li", parent=B, leftIndent=16, bulletIndent=2, spaceAfter=5)
KL = ParagraphStyle("kl", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUT)
KV = ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK)
KD = ParagraphStyle("kd", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUT)

ANCHO = letter[0] - 3.6 * cm


def _md(texto: str) -> str:
    """Convierte el **negritas** de las recomendaciones al formato de reportlab."""
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)


def _ejes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c9ccd1")
    ax.tick_params(colors=SUAVE, labelsize=8)
    ax.grid(axis="y", color="#e6e8eb", linewidth=0.8)
    ax.set_axisbelow(True)


def _pesos(ax, eje="y"):
    fmt = mtick.FuncFormatter(lambda v, _: f"${v / 1000:,.0f}k" if abs(v) >= 1000 else f"${v:,.0f}")
    (ax.yaxis if eje == "y" else ax.xaxis).set_major_formatter(fmt)


def _imagen(fig, ancho=ANCHO) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    alto = ancho * fig.get_figheight() / fig.get_figwidth()
    return Image(buf, width=ancho, height=alto)


def _grafica(titulo: str, pregunta: str, img: Image) -> KeepTogether:
    return KeepTogether([Paragraph(_md(titulo), H3), Paragraph(pregunta, PQ), img, Spacer(1, 6)])


# ---------------------------------------------------------------- gráficas
def _g_tendencia(d):
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.plot(d.index, d["ventas"], color=AZUL, alpha=0.3, lw=0.8, label="Venta diaria")
    ax.plot(d.index, d["media_7d"], color=AZUL, lw=2, label="Promedio de 7 días")
    _ejes(ax), _pesos(ax)
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    return fig


def _g_histograma(tk, bins):
    fig, ax = plt.subplots(figsize=(4.5, 2.9))
    tope = tk.quantile(0.99)
    ax.hist(tk[tk <= tope], bins=bins, color=AZUL, edgecolor="white", linewidth=1)
    ax.axvline(tk.median(), color=NARANJA, ls="--", lw=1.5)
    ax.text(tk.median(), ax.get_ylim()[1] * 0.95, f" Mediana ${tk.median():,.0f}", color=TINTA, fontsize=8, va="top")
    _ejes(ax), _pesos(ax, "x")
    ax.set_xlabel("Total del pedido", fontsize=8, color=SUAVE)
    ax.set_ylabel("Pedidos", fontsize=8, color=SUAVE)
    return fig


def _g_calor(tabla):
    fig, ax = plt.subplots(figsize=(4.5, 2.9))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("azules", ["#f3f7fd", "#9cc3f0", AZUL, "#0d3f80"])
    im = ax.imshow(tabla.values, aspect="auto", cmap=cmap)
    ax.set_yticks(range(len(tabla.index)), tabla.index, fontsize=7.5, color=SUAVE)
    ax.set_xticks(range(len(tabla.columns)), [f"{h}h" for h in tabla.columns], fontsize=6.5, color=SUAVE, rotation=90)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=7, colors=SUAVE)
    cb.outline.set_visible(False)
    return fig


def _g_dispersion(x, m, b):
    fig, ax = plt.subplots(figsize=(4.5, 2.9))
    n, q = x[~x["quincena"]], x[x["quincena"]]
    ax.scatter(n["tickets"], n["ventas"], s=14, color=AZUL, alpha=0.6, edgecolor="white", linewidth=0.5, label="Día normal")
    ax.scatter(q["tickets"], q["ventas"], s=14, color=NARANJA, alpha=0.8, edgecolor="white", linewidth=0.5, label="Día de quincena")
    if not np.isnan(m):
        xs = np.array([x["tickets"].min(), x["tickets"].max()])
        ax.plot(xs, m * xs + b, color=GRIS, ls="--", lw=1.5, label="Tendencia")
    _ejes(ax), _pesos(ax)
    ax.set_xlabel("Pedidos en el día", fontsize=8, color=SUAVE)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    return fig


def _g_espectro(esp, info):
    fig, ax = plt.subplots(figsize=(4.5, 2.9))
    ax.plot(esp["periodo"], esp["potencia"], color=AZUL, lw=1.4)
    ax.set_yscale("log")
    for nombre, p in (("Semanal", info["semanal"]), ("Quincena", info["quincena"])):
        if p is not None:
            ax.annotate(f"{nombre}: {p['periodo']:.1f} días", (p["periodo"], p["potencia"]),
                        xytext=(12, 10), textcoords="offset points", fontsize=7.5, color=TINTA,
                        arrowprops=dict(arrowstyle="-", color=SUAVE, lw=0.8))
    _ejes(ax)
    ax.set_xlabel("Periodo del ciclo (días)", fontsize=8, color=SUAVE)
    ax.set_ylabel("Potencia relativa", fontsize=8, color=SUAVE)
    return fig


def _g_categorias(tabla_m, color_cat):
    fig, ax = plt.subplots(figsize=(9, 3))
    orden = list(tabla_m.sum().sort_values(ascending=False).index)
    etiquetas = [f"{MESES[t.month - 1]} {str(t.year)[2:]}" for t in tabla_m.index]
    base = np.zeros(len(tabla_m))
    for cat in orden:
        ax.bar(range(len(tabla_m)), tabla_m[cat].values, bottom=base, color=color_cat.get(cat, GRIS),
               edgecolor="white", linewidth=1, label=cat, width=0.8)
        base += tabla_m[cat].values
    paso = max(1, int(np.ceil(len(etiquetas) / 9)))
    ax.set_xticks(range(0, len(etiquetas), paso), etiquetas[::paso], fontsize=7.5)
    ax.set_xlim(-0.6, len(etiquetas) - 0.4)
    _ejes(ax), _pesos(ax)
    ax.legend(frameon=False, fontsize=7.5, ncol=len(orden), loc="upper center", bbox_to_anchor=(0.5, -0.12))
    return fig


# ---------------------------------------------------------------- reporte
def _kpis(k, estrella):
    def celda(etq, valor, detalle):
        return [Paragraph(etq, KL), Paragraph(valor, KV), Paragraph(detalle, KD)]
    var = k["variacion"]
    var_txt = "sin semana previa" if np.isnan(var) else f"{var:+.1f}% vs. semana anterior"
    celdas = [celda("Ventas del periodo", f"${k['ventas']:,.0f}", f"{k['n_tickets']:,} pedidos"),
              celda("Ticket promedio", f"${k['ticket_prom']:,.0f}", "por pedido"),
              celda("Producto estrella", estrella, f"{k['estrella_pct']:.0f}% de las ventas"),
              celda("Últimos 7 días", f"${k['semana']:,.0f}", var_txt)]
    t = Table([celdas], colWidths=[ANCHO / 4] * 4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEAFTER", (0, 0), (-2, -1), 1, colors.white),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9)]))
    return t


def _resumen(an, df, d, info, tabla):
    sem = an.dias_semana(d)
    alto, bajo = sem.idxmax(), sem.idxmin()
    horas = tabla.sum()
    puntos = []
    m = d["ventas"].resample("MS").sum()
    m = m[m.index + pd.offsets.MonthEnd(0) <= d.index.max()]
    if len(m) >= 13 and m.iloc[-13] > 0:
        cambio = (m.iloc[-1] / m.iloc[-13] - 1) * 100
        puntos.append(f"<b>Crecimiento:</b> el último mes completo vendió {cambio:+.0f}% contra el mismo mes del año anterior.")
    if sem[bajo] > 0:
        puntos.append(f"<b>Semana:</b> el {alto} es el mejor día; vende {sem[alto] / sem[bajo]:.1f} veces lo del {bajo}.")
    if horas.sum() > 0:
        noche = horas[horas.index >= 19].sum() / horas.sum() * 100
        puntos.append(f"<b>Horario:</b> el {noche:.0f}% de las ventas entra por mensajes de 19 h en adelante; "
                      f"la hora pico es a las {horas.idxmax()} h.")
    if not np.isnan(info["efecto_quincena"]):
        puntos.append(f"<b>Quincena:</b> los días 15-16 y 30-1 venden {info['efecto_quincena']:+.0f}% "
                      f"contra un día normal.")
    return puntos


def generar(an, df: pd.DataFrame, periodo: str, color_cat: dict | None = None) -> bytes:
    """Arma el PDF y lo regresa como bytes (para st.download_button)."""
    if not color_cat:  # mismo criterio que el tablero: color fijo por ventas totales
        orden_cat = df.groupby("categoria")["total"].sum().sort_values(ascending=False).index
        color_cat = {c: CATEGORIAS[i % len(CATEGORIAS)] for i, c in enumerate(orden_cat)}
    d = an.diario(df)
    k = an.kpis(df)
    serie, t1 = an.tendencia(d)
    tk, bins, t2 = an.histograma(df)
    tabla, t3 = an.mapa_calor(df)
    x, m, b, t4 = an.dispersion(d)
    esp, info, t5 = an.espectro(d)
    tabla_m, t6 = an.productos_mes(df)
    recs = an.recomendaciones(df, d, info, tabla)
    estrella = k["estrella"].split(" (")[0]

    st = [Paragraph("Reporte gerencial · Salomé", H1), Spacer(1, 3),
          Paragraph(f"Periodo analizado: {periodo} · Generado el {datetime.now():%d/%m/%Y %H:%M}", SUB),
          Paragraph("Preparado por DulceDato Analytics", SUB), Spacer(1, 10),
          _kpis(k, estrella), Spacer(1, 6),
          Paragraph("Resumen", H2)]
    st += [Paragraph(p, LI, bulletText="•") for p in _resumen(an, df, d, info, tabla)]
    st += [Paragraph("Qué hacer esta semana", H2)]
    st += [Paragraph(_md(r), LI, bulletText=f"{i}.") for i, r in enumerate(recs, 1)]

    st.append(Spacer(1, 4))
    st.append(_grafica(t1, "¿Mi negocio está creciendo?", _imagen(_g_tendencia(serie))))
    st += [PageBreak(), Paragraph("Lo que dicen los datos", H2)]
    st.append(_grafica(t6, "¿Qué vendo en cada temporada?", _imagen(_g_categorias(tabla_m, color_cat))))

    mitad = (ANCHO - 0.6 * cm) / 2
    def par(a, b_):
        t = Table([[a, b_]], colWidths=[mitad + 0.3 * cm] * 2)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
        return t
    bloque = lambda ti, pr, fig: [Paragraph(_md(ti), H3), Paragraph(pr, PQ), _imagen(fig, mitad)]
    st.append(par(bloque(t2, "¿Cuánto gasta un cliente por pedido?", _g_histograma(tk, bins)),
                  bloque(t3, "¿A qué hora y qué día llegan los pedidos?", _g_calor(tabla))))
    st.append(Spacer(1, 8))
    if len(x) >= 7 and not esp.empty:
        st.append(par(bloque(t4, "¿Vendo más por más pedidos o por pedidos más grandes?", _g_dispersion(x, m, b)),
                      bloque(t5, "¿Mis ventas siguen ciclos? (análisis espectral)", _g_espectro(esp, info))))
        st.append(Paragraph(
            "<b>Cómo leer el análisis de ciclos:</b> cada pico es un patrón que se repite. El de 7 días es la semana "
            "(se vende más de viernes a domingo) y el de cerca de 15 días es la quincena, cuando los clientes cobran. "
            "Planear la producción con estos dos ciclos reduce lo que se tira y los pedidos que se rechazan.", B))
    elif len(x) >= 7:
        st.append(KeepTogether(bloque(t4, "¿Vendo más por más pedidos o por pedidos más grandes?", _g_dispersion(x, m, b))))
        st.append(Paragraph("El análisis de ciclos necesita al menos 6 semanas de datos; amplía el periodo para verlo.", PQ))

    def pie(c, doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(MUT)
        c.drawString(1.8 * cm, 1.2 * cm, "Salomé · Reporte gerencial · DulceDato Analytics")
        c.drawRightString(letter[0] - 1.8 * cm, 1.2 * cm, f"Página {doc.page}")
        c.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                      bottomMargin=1.8 * cm, title="Reporte gerencial · Salomé",
                      author="DulceDato Analytics").build(st, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
