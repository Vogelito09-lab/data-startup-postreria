"""Genera las figuras y los números que citan los documentos de E1 y E2.

    python scripts/figuras_docs.py

E1 usa el historial hasta el 24 de octubre de 2026 (lo que había al entregar E1).
E2 usa todo, incluida la semana del 25 al 31 de octubre que se sube en la demostración.
Los números quedan en docs/resultados.json para que el texto y las figuras no se contradigan.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "services" / "tablero"))
sys.path.insert(0, str(RAIZ / "services" / "worker"))
import analitica as an  # noqa: E402
import modelos_e2 as m2  # noqa: E402
from limpieza import limpiar  # noqa: E402

IMG = RAIZ / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
CAFE, ROSA, CREMA, GRIS, AZUL = "#7a4a2e", "#d97a8c", "#e9c46a", "#8d8d8d", "#6a9fb5"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titlesize": 11, "axes.titleweight": "bold",
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def guardar(fig, nombre):
    fig.savefig(IMG / nombre)
    plt.close(fig)


def miles(ax, eje="y"):
    f = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    (ax.yaxis if eje == "y" else ax.xaxis).set_major_formatter(f)


def envolver(texto, n=70):
    import textwrap
    return "\n".join(textwrap.wrap(texto, n))


res = {}
cierres = pd.read_csv(RAIZ / "services/worker/referencia/calendario_cierres.csv")["fecha"]

# ======================= E1
crudo = pd.read_csv(RAIZ / "data/historial/historial_hasta_2026-10-24.csv", dtype=str)
limpio, rep = limpiar(crudo)
df = an.preparar(limpio)
t = an.titulos(df)
k = t["kpi"]
dsem = an.por_dia_semana(df)
esp = an.espectro(an.serie_diaria(df))
pk = an.picos(esp, n=6)
q = an.prueba_quincena(df)
recs = an.recomendaciones(df)
ped = an.pedidos_por_pedido(df)
mh = an.mapa_dia_hora(df)
res["e1"] = {
    "limpieza": rep.como_dict(), "periodo": [str(df.fecha_entrega.min().date()), str(df.fecha_entrega.max().date())],
    "pedidos": int(df.pedido_id.nunique()), "renglones": len(df), "clientes": int(df.cliente_id.nunique()),
    "productos": sorted(df.producto.unique()), "kpi": {kk: (str(v) if isinstance(v, pd.Timestamp) else float(v) if isinstance(v, (int, float, np.number)) else v) for kk, v in k.items()},
    "titulos": {kk: v for kk, v in t.items() if kk != "kpi"},
    "dia_semana": {an.DIAS[i]: round(float(v)) for i, v in dsem.items() if pd.notna(v)},
    "picos": pk[["periodo", "potencia_relativa"]].round(3).to_dict("records"),
    "potencia_15": an.potencia_cerca(esp, 15.2) / pk.potencia.iloc[0],
    "potencia_30": an.potencia_cerca(esp, 30.4) / pk.potencia.iloc[0],
    "quincena": q, "recomendaciones": recs,
    "ticket_p90": float(ped.total.quantile(.9)), "bins_sturges": int(np.ceil(np.log2(len(ped)) + 1)),
    "noche": float((ped.hora.dropna() >= 19).mean()),
    "por_anio": {int(a): {"venta": float(g.total.sum()), "pedidos": int(g.pedido_id.nunique()), "piezas": int(g.unidades.sum())}
                 for a, g in df.groupby(df.fecha_entrega.dt.year)},
    "venta_mensual_2025": float(an.mensual(df[df.fecha_entrega.dt.year == 2025]).mean()),
    "por_categoria": (df.groupby("categoria").total.sum() / df.total.sum()).round(3).to_dict(),
    "por_canal_2026": (df[df.fecha_entrega.dt.year == 2026].groupby("canal").pedido_id.nunique() /
                       df[df.fecha_entrega.dt.year == 2026].pedido_id.nunique()).round(3).to_dict(),
}

# 1 líneas
m = an.mensual(df)
m = m[m.index < "2026-10"]
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(m.index.to_timestamp(), m.values, color=CAFE, lw=2)
ax.set_title(envolver(t["lineas"], 95))
miles(ax)
ax.grid(axis="y", color="#eee")
guardar(fig, "e1_1_lineas.png")

# 2 histograma
fig, ax = plt.subplots(figsize=(6.5, 3.6))
ax.hist(ped.total, bins=res["e1"]["bins_sturges"], color=ROSA, edgecolor="white")
ax.axvline(ped.total.median(), color=CAFE, ls="--", label=f"mediana {an.pesos(ped.total.median())}")
ax.set_xlabel("Total del pedido")
ax.set_ylabel("Pedidos")
ax.legend(frameon=False)
miles(ax, "x")
ax.set_title(envolver(t["histograma"], 65))
guardar(fig, "e1_2_histograma.png")

# 3 mapa de calor
fig, ax = plt.subplots(figsize=(9, 3.4))
im = ax.imshow(mh.values, aspect="auto", cmap="copper_r")
ax.set_yticks(range(7), [d.capitalize() for d in an.DIAS])
ax.set_xticks(range(len(mh.columns)), [f"{int(h)}" for h in mh.columns])
ax.set_xlabel("Hora en que llegó el mensaje")
fig.colorbar(im, ax=ax, label="Pedidos")
ax.set_title(envolver(t["calor"], 95))
guardar(fig, "e1_3_calor.png")

# 4 dispersión
dia = df.groupby("fecha_entrega").agg(pedidos=("pedido_id", "nunique"), venta=("total", "sum"))
esp_d = an.es_fecha_especial(dia.index)
fig, ax = plt.subplots(figsize=(6.5, 3.8))
ax.scatter(dia.pedidos[~esp_d], dia.venta[~esp_d], s=9, alpha=.35, color=ROSA, label="Día normal")
ax.scatter(dia.pedidos[esp_d], dia.venta[esp_d], s=16, alpha=.9, color=CAFE, label="Fecha especial")
p = np.polyfit(dia.pedidos, dia.venta, 1)
xs = np.array([1, dia.pedidos.max()])
ax.plot(xs, np.polyval(p, xs), color=GRIS, ls="--", label="Ajuste lineal")
ax.set_xlabel("Pedidos entregados en el día")
ax.set_ylabel("Venta del día")
miles(ax)
ax.legend(frameon=False)
ax.set_title(envolver(t["dispersion"], 65))
res["e1"]["dispersion"] = {"pendiente": float(p[0]), "r": float(np.corrcoef(dia.pedidos, dia.venta)[0, 1])}
guardar(fig, "e1_4_dispersion.png")

# 5 espectro
e = esp[(esp.periodo >= 2) & (esp.periodo <= 35)]
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.plot(e.periodo, e.potencia / pk.potencia.iloc[0], color=CAFE, lw=1)
for per, txt in ((3.5, "3.5"), (7, "7 días"), (15.2, "quincena"), (30.4, "mes")):
    ax.axvline(per, color=ROSA, ls=":", lw=1)
    ax.text(per, 1.02, txt, ha="center", color=ROSA, fontsize=9)
ax.set_xlabel("Periodo en días (T = 1/f)")
ax.set_ylabel("Potencia relativa a la semana")
ax.set_xlim(2, 35)
ax.set_title(envolver(t["espectro"], 95), pad=16)
guardar(fig, "e1_5_espectro.png")

# 6 barras apiladas
cat = df.assign(mes=df.fecha_entrega.dt.month).groupby(["mes", "categoria"])["total"].sum().unstack(fill_value=0)
dias_mes = df.assign(mes=df.fecha_entrega.dt.month).groupby("mes")["fecha_entrega"].nunique()
cat = cat.div(dias_mes, axis=0)
colores = {"Pasteles enteros": CAFE, "Rebanadas": ROSA, "Galletas y brownies": CREMA, "Eventos": AZUL, "Temporada": "#9b6fb0"}
fig, ax = plt.subplots(figsize=(9, 3.6))
abajo = np.zeros(len(cat))
for c in ["Pasteles enteros", "Rebanadas", "Galletas y brownies", "Eventos", "Temporada"]:
    ax.bar([an.MESES[i - 1][:3] for i in cat.index], cat[c], bottom=abajo, color=colores[c], label=c)
    abajo += cat[c].to_numpy()
ax.set_ylabel("Venta promedio por día con entregas")
miles(ax)
ax.legend(frameon=False, ncol=5, fontsize=8, loc="upper left")
ax.set_ylim(0, abajo.max() * 1.15)
ax.set_title(envolver(t["barras"], 95))
guardar(fig, "e1_6_barras.png")

# ======================= E2
completo = an.preparar(pd.read_csv(RAIZ / "data/historial/pedidos_salome_clean.csv"))
s = an.serie_diaria(completo)
s22 = s[s.index >= m2.INICIO_MODELO]
stl = m2.descomposicion(completo)
dm = m2.descomposicion_mensual(completo)
from statsmodels.tsa.stattools import acf, pacf  # noqa: E402
mens = completo.groupby(completo.fecha_entrega.dt.to_period("M")).total.sum()
mens = mens[(mens.index >= "2020-03") & (mens.index <= "2026-10")]
res["e2"] = {
    "adf": {
        "diaria_2022": m2.adf(s22), "diaria_2022_ct": m2.adf(s22, "ct"), "diaria_completa_ct": m2.adf(s, "ct"),
        "diaria_dif7": m2.adf(s22.diff(7)), "mensual_completa": m2.adf(mens.astype(float)),
        "mensual_dif1": m2.adf(mens.astype(float).diff()),
    },
    "acf": np.round(acf(s22, nlags=28), 3).tolist(), "pacf": np.round(pacf(s22, nlags=28), 3).tolist(),
    "stl_var": {"tendencia": float(stl.trend.var() / stl.observed.var()), "semanal": float(stl.seasonal.var() / stl.observed.var()),
                "residuo": float(stl.resid.var() / stl.observed.var())},
    "estacional_semana": {an.DIAS[i]: round(float(v)) for i, v in stl.seasonal.groupby(stl.seasonal.index.dayofweek).mean().items()},
    "estacional_mes": {an.MESES[i.month - 1]: round(float(v), 3) for i, v in dm.seasonal.iloc[:12].sort_index(key=lambda x: x.month).items()},
}
r = m2.ajustar(completo, cierres)
rq = m2.ajustar(completo, cierres, cuadratica=True)
d = m2.datos_modelo(completo, cierres)
X = m2.matriz_diseno(d.index)
va, tr2 = (d.index >= "2025-01-01") & (d.index < m2.CORTE_PRUEBA), d.index < "2025-01-01"
val = {}
for nombre, cuad in (("lineal", False), ("cuadratica", True)):
    Xv = m2.matriz_diseno(d.index, cuadratica=cuad)
    b = m2.mco(Xv[tr2].to_numpy(), d.venta[tr2].to_numpy())
    val[nombre] = m2.metricas(d.venta[va].to_numpy(), Xv[va].to_numpy() @ b)
e_ = r["residuos"]
from statsmodels.stats.diagnostic import het_breuschpagan  # noqa: E402
from statsmodels.stats.stattools import durbin_watson  # noqa: E402
bp = het_breuschpagan(e_, m2.matriz_diseno(r["fechas_tr"]).to_numpy())
sw = stats.shapiro(e_[:5000])
res["e2"]["regresion"] = {
    "beta": r["beta"].round(2).to_dict(), "beta_sklearn": r["beta_sklearn"].round(2).to_dict(),
    "dif_max_sklearn": r["dif_max_sklearn"], "dif_pred_sklearn": r["dif_pred_sklearn"], "condicion": r["condicion_XtX"],
    "entrenamiento": r["metricas_entrenamiento"], "prueba": r["metricas_prueba"], "ingenuo": r["metricas_ingenuo_prueba"],
    "sklearn_prueba": r["metricas_sklearn_prueba"], "n_tr": r["n_tr"], "n_te": r["n_te"], "p": int(X.shape[1]),
    "cuadratica_prueba": rq["metricas_prueba"], "validacion_2025": val,
    "sesgo_prueba": float(np.mean(r["y_te"] - r["pred_te"])), "sesgo_prueba_cuadratica": float(np.mean(rq["y_te"] - rq["pred_te"])),
    "residuos": {"media": float(e_.mean()), "asimetria": float(stats.skew(e_)), "curtosis_exceso": float(stats.kurtosis(e_)),
                 "durbin_watson": float(durbin_watson(e_)), "breusch_pagan_p": float(bp[1]), "shapiro_p": float(sw.pvalue),
                 "acf_1_7": np.round(acf(e_, nlags=7)[1:], 3).tolist(),
                 "corr_abs_ajustado": float(np.corrcoef(np.abs(e_), r["pred_tr"])[0, 1])},
    "venta_media_dia_abierto_prueba": float(np.mean(r["y_te"])),
}

# STL
ult = slice(pd.Timestamp("2026-05-01"), None)
fig, axs = plt.subplots(4, 1, figsize=(9, 7), sharex=True)
for ax, (nom, ser, col) in zip(axs, [("Venta observada", stl.observed, ROSA), ("Tendencia", stl.trend, CAFE),
                                     ("Estacionalidad semanal (periodo 7)", stl.seasonal, CREMA), ("Residuo", stl.resid, GRIS)]):
    ser = ser[ult]
    if nom == "Residuo":
        ax.scatter(ser.index, ser.values, s=5, color=col)
        ax.axhline(0, color="black", lw=.6)
    else:
        ax.plot(ser.index, ser.values, color=col, lw=1.3)
    ax.set_title(nom, loc="left", fontsize=10)
    miles(ax)
fig.suptitle(envolver(f"El ciclo semanal explica {res['e2']['stl_var']['semanal']:.0%} de la variación diaria; el residuo "
                      f"se lleva {res['e2']['stl_var']['residuo']:.0%} (STL desde 2022; se muestran mayo a octubre de 2026)", 95), fontweight="bold")
guardar(fig, "e2_1_stl_semanal.png")

# Descomposición mensual
fig, axs = plt.subplots(3, 1, figsize=(9, 5.6), sharex=True)
axs[0].plot(dm.observed.index, dm.observed.values, color=ROSA)
axs[0].plot(dm.trend.index, dm.trend.values, color=CAFE, lw=2)
axs[0].set_title("Venta mensual y su tendencia (media móvil de 12 meses)", loc="left", fontsize=10)
miles(axs[0])
axs[1].bar(dm.seasonal.index, dm.seasonal.values - 1, width=25, color=[CAFE if v > 1 else ROSA for v in dm.seasonal.values])
axs[1].set_title("Índice estacional (multiplicativo, % sobre la tendencia)", loc="left", fontsize=10)
axs[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
axs[2].plot(dm.resid.index, dm.resid.values, "o-", ms=3, color=GRIS)
axs[2].axhline(1, color="black", lw=.6)
axs[2].set_title("Residuo", loc="left", fontsize=10)
fig.suptitle("La tendencia mensual se aplana desde 2023; mayo y diciembre son los meses altos", fontweight="bold")
guardar(fig, "e2_2_descomposicion_mensual.png")

# ACF / PACF
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf  # noqa: E402
fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
plot_acf(s22, lags=28, ax=axs[0], color=CAFE, vlines_kwargs={"colors": CAFE})
plot_pacf(s22, lags=28, ax=axs[1], color=CAFE, vlines_kwargs={"colors": CAFE}, method="ywm")
axs[0].set_title("ACF: picos en 7, 14, 21 y 28 que bajan despacio")
axs[1].set_title("PACF: picos en 7 y 14; el rezago 1 casi no pesa")
for ax in axs:
    ax.set_xlabel("Rezago (días)")
    ax.set_xticks([0, 7, 14, 21, 28])
guardar(fig, "e2_3_acf_pacf.png")

# Regresión: prueba
idx = pd.date_range(m2.INICIO_MODELO, completo.fecha_entrega.max(), freq="D")
abiertos = m2.dias_abiertos(pd.Series(0, index=idx), cierres)
sem = s.reindex(idx).resample("W-SUN").sum()
pred = m2.predecir(r, idx).where(abiertos, 0).clip(lower=0).resample("W-SUN").sum()
tend = m2.tendencia(r, idx).resample("W-SUN").mean() * 6
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.axvspan(pd.Timestamp(m2.CORTE_PRUEBA), idx.max(), color="#f1f1f1")
ax.text(pd.Timestamp(m2.CORTE_PRUEBA), sem.max() * .97, "  año de prueba", fontsize=9, color=GRIS)
ax.plot(sem.index, sem.values, color=ROSA, lw=1, label="Venta real por semana")
ax.plot(pred.index, pred.values, color=CAFE, lw=1, label="Regresión")
ax.plot(tend.index, tend.values, color="black", lw=2, ls="--", label="Línea de tendencia")
miles(ax)
ax.legend(frameon=False, ncol=3, loc="upper left")
ax.set_ylim(0, sem.max() * 1.12)
ax.set_title(envolver(f"La regresión sigue el calendario pero no los días raros: en el año de prueba se equivoca "
                      f"{an.pesos(r['metricas_prueba']['MAE'])} por día (R² = {r['metricas_prueba']['R2']:.2f})", 95))
guardar(fig, "e2_4_regresion.png")

# Residuos
from statsmodels.graphics.gofplots import qqplot  # noqa: E402
fig, axs = plt.subplots(2, 2, figsize=(10, 6.6))
axs[0, 0].scatter(r["pred_tr"], e_, s=6, alpha=.4, color=CAFE)
axs[0, 0].axhline(0, color="black", lw=.7)
axs[0, 0].set_xlabel("Venta ajustada")
axs[0, 0].set_ylabel("Residuo")
axs[0, 0].set_title("Residuo contra ajuste: el abanico se abre")
miles(axs[0, 0], "x")
axs[0, 1].hist(e_, bins=int(np.ceil(np.log2(len(e_)) + 1)), color=ROSA, edgecolor="white")
axs[0, 1].set_title(f"Distribución: asimetría {stats.skew(e_):.2f}")
miles(axs[0, 1], "x")
qqplot(e_, line="s", ax=axs[1, 0], markersize=2, color=CAFE)
axs[1, 0].set_title("Q-Q contra la normal: cola derecha más pesada")
plot_acf(e_, lags=21, ax=axs[1, 1], color=CAFE, vlines_kwargs={"colors": CAFE})
axs[1, 1].set_title(f"ACF del residuo: Durbin-Watson {durbin_watson(e_):.2f}")
fig.tight_layout()
guardar(fig, "e2_5_residuos.png")

(RAIZ / "docs" / "resultados.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
print(json.dumps({"e1_kpi": res["e1"]["kpi"], "e1_limpieza": res["e1"]["limpieza"], "picos": res["e1"]["picos"],
                  "quincena": res["e1"]["quincena"], "adf": res["e2"]["adf"], "reg": {kk: v for kk, v in res["e2"]["regresion"].items() if kk not in ("beta", "beta_sklearn")}},
                 indent=1, ensure_ascii=False, default=str))
