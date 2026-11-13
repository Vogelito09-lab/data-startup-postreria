"""E3 · Entrena, evalúa y versiona los modelos.

    python scripts/entrenar_e3.py

1. SARIMA de la venta diaria: búsqueda de órdenes por AIC/BIC, evaluación con origen
   móvil (cada semana del año de prueba se pronostican los 7 días siguientes con lo que se
   sabía hasta ese día), banda de confianza del 95%.
2. Clasificador "¿mañana se entregan 2 o más pasteles enteros?": cuatro modelos con
   validación cruzada temporal, matriz de confusión, precisión, recall y F1.
3. Reentrena con toda la historia y guarda models/<nombre>_v<N>.pkl + models/registro.json.
"""
import hashlib
import itertools
import json
import pickle
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "services/tablero"), str(RAIZ / "services/modelos")]
import analitica as an  # noqa: E402
import modelos_e2 as m2  # noqa: E402
import nucleo as nu  # noqa: E402

IMG, MODELOS = RAIZ / "docs/img", RAIZ / "models"
MODELOS.mkdir(exist_ok=True)
CAFE, ROSA, CREMA, GRIS, AZUL = "#7a4a2e", "#d97a8c", "#e9c46a", "#8d8d8d", "#6a9fb5"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "figure.dpi": 150, "savefig.bbox": "tight"})
VERSION = 1


def metr(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    m = ~np.isnan(y) & ~np.isnan(p)
    e = y[m] - p[m]
    return {"MAE": float(np.mean(np.abs(e))), "RMSE": float(np.sqrt(np.mean(e ** 2))), "n": int(m.sum())}


ruta = RAIZ / "data/historial/pedidos_salome_clean.csv"
crudo = pd.read_csv(ruta)
df = an.preparar(crudo)
cierres = an.cierres_registrados()
res = {"datos": {"archivo": ruta.name, "renglones": len(df), "pedidos": int(df.pedido_id.nunique()),
                 "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()[:16],
                 "hasta": str(df.fecha_entrega.max().date())}}

# ============================================================ 1. SARIMA
y = nu.serie_sarima(df, cierres=cierres)
ytr = y[y.index < nu.CORTE_PRUEBA]
t0 = time.time()
filas = []
for p, q, P, D, Q in itertools.product([0, 1, 2], [0, 1, 2], [0, 1], [0, 1], [0, 1]):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    try:
        r = SARIMAX(ytr, order=(p, 0, q), seasonal_order=(P, D, Q, 7), trend="c" if D == 0 else "n").fit(disp=False, maxiter=300)
        filas.append({"p": p, "d": 0, "q": q, "P": P, "D": D, "Q": Q, "aic": r.aic, "bic": r.bic, "parametros": len(r.params)})
    except Exception:  # noqa: BLE001
        pass
busqueda = pd.DataFrame(filas).sort_values("aic").reset_index(drop=True)
res["sarima_busqueda_segundos"] = round(time.time() - t0, 1)
res["sarima_top"] = busqueda.head(8).round(1).to_dict("records")
res["sarima_mejor_D0"] = busqueda[busqueda.D == 0].head(1).round(1).to_dict("records")
print(busqueda.head(8))

# Evaluación con origen móvil en el año de prueba, para los 3 mejores por AIC y el más simple por BIC
cand = busqueda.head(3).to_dict("records") + busqueda.sort_values("bic").head(1).to_dict("records")
vistos, evaluacion = set(), {}
origenes = pd.date_range(nu.CORTE_PRUEBA, y.index.max() - pd.Timedelta(days=6), freq="7D")


def origen_movil(res_fit, serie):
    pred = pd.Series(np.nan, index=serie.index)
    sup = pred.copy()
    inf = pred.copy()
    for o in origenes:
        r_o = res_fit.apply(serie[serie.index < o])
        f = nu.pronostico(r_o, 7, cierres)
        pred.loc[f.index] = f.pronostico
        sup.loc[f.index] = f.superior
        inf.loc[f.index] = f.inferior
    return pred, inf, sup


for c in cand:
    clave = (c["p"], c["q"], c["P"], c["D"], c["Q"])
    if clave in vistos:
        continue
    vistos.add(clave)
    fit = nu.ajustar_sarima(ytr, (c["p"], 0, c["q"]), (c["P"], c["D"], c["Q"], 7))
    pred, inf, sup = origen_movil(fit, y)
    te = (y.index >= nu.CORTE_PRUEBA) & an.abiertos(y.index, cierres)
    nombre = f"SARIMA({c['p']},0,{c['q']})({c['P']},{c['D']},{c['Q']})7"
    cobertura = float(((y[te] >= inf[te]) & (y[te] <= sup[te])).mean())
    evaluacion[nombre] = metr(y[te], pred[te]) | {"aic": round(c["aic"], 1), "bic": round(c["bic"], 1),
                                                  "parametros": int(c["parametros"]), "cobertura_95": cobertura}
    print(nombre, evaluacion[nombre])

# Líneas base en exactamente los mismos días
s_full = an.serie_diaria(df)
te_idx = y.index[(y.index >= nu.CORTE_PRUEBA) & an.abiertos(y.index, cierres)]
ingenuo = s_full.shift(7).reindex(te_idx)
r2 = m2.ajustar(df, cierres)
reg = pd.Series(r2["pred_te"], index=r2["fechas_te"]).reindex(te_idx)
prom = ytr.groupby(ytr.index.dayofweek).mean()
promedio_dia = pd.Series(prom.reindex(te_idx.dayofweek).to_numpy(), index=te_idx)
evaluacion["Ingenuo estacional (mismo día semana pasada)"] = metr(y[te_idx], ingenuo)
evaluacion["Regresión de E2"] = metr(y[te_idx], reg)
evaluacion["Promedio por día de la semana"] = metr(y[te_idx], promedio_dia)
res["sarima_evaluacion"] = evaluacion

# Elegido: el de menor BIC (castiga más los parámetros que el AIC). El año de prueba solo se usa
# para confirmar que no pierde contra los otros candidatos, no para elegir.
sar = {k: v for k, v in evaluacion.items() if k.startswith("SARIMA")}
elegido = min(sar, key=lambda k: sar[k]["bic"])
res["sarima_elegido"] = elegido
num = [int(x) for x in elegido.replace("SARIMA(", "").replace(")7", "").replace(")(", ",").split(",")]
orden, estacional = (num[0], num[1], num[2]), (num[3], num[4], num[5], 7)

# Gráfica del año de prueba
fit_e = nu.ajustar_sarima(ytr, orden, estacional)
pred, inf, sup = origen_movil(fit_e, y)
ult = (y.index >= "2026-08-01")
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.fill_between(y.index[ult], inf[ult], sup[ult], color=CREMA, alpha=.45, label="Banda de 95%")
ax.plot(y.index[ult], y[ult], "o", ms=3, color=ROSA, label="Venta real")
ax.plot(y.index[ult], pred[ult], color=CAFE, lw=1.4, label="Pronóstico a 7 días")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
ax.legend(frameon=False, ncol=3, loc="upper left")
ax.set_ylim(0, max(sup[ult].max(), y[ult].max()) * 1.15)
ev = evaluacion[elegido]
ax.set_title(f"{elegido}: se equivoca {an.pesos(ev['MAE'])} por día y la banda contiene {ev['cobertura_95']:.0%} de los días reales",
             fontsize=10)
fig.savefig(IMG / "e3_1_sarima_prueba.png")
plt.close(fig)

# Diagnóstico de residuos del elegido
from statsmodels.stats.diagnostic import acorr_ljungbox  # noqa: E402
resid = fit_e.resid[fit_e.resid.index >= ytr.index[14]].dropna()
lb = acorr_ljungbox(resid, lags=[7, 14], return_df=True)
res["sarima_ljung_box"] = {int(k): float(v) for k, v in lb["lb_pvalue"].items()}
res["sarima_parametros"] = {k: round(float(v), 4) for k, v in fit_e.params.items()}
res["sarima_pvalores"] = {k: round(float(v), 4) for k, v in fit_e.pvalues.items()}

# Mismo orden para pasteles enteros (lo que Salomé hornea)
ye = nu.serie_sarima(df, "enteros", cierres)
fit_ent = nu.ajustar_sarima(ye[ye.index < nu.CORTE_PRUEBA], orden, estacional)
pe, ie, se = origen_movil(fit_ent, ye)
te_e = (ye.index >= nu.CORTE_PRUEBA) & an.abiertos(ye.index, cierres)
res["sarima_enteros"] = metr(ye[te_e], pe[te_e]) | {
    "cobertura_95": float(((ye[te_e] >= ie[te_e]) & (ye[te_e] <= se[te_e])).mean()),
    "ingenuo": metr(ye[te_e], an.serie_diaria(df[df.categoria.isin(nu.ENTEROS)], "unidades").shift(7).reindex(ye.index[te_e]))}

# ============================================================ 2. Clasificador
from sklearn.metrics import confusion_matrix, f1_score, fbeta_score, make_scorer, precision_score, recall_score, roc_auc_score  # noqa: E402

# Un día fuerte que no se ve venir cuesta más (pedidos rechazados, unos $500 cada uno) que una base de
# cheesecake de más (unos $150 de insumos que se pueden vender en rebanadas). Por eso el criterio es F2,
# que pesa el recall el doble que la precisión. Se decidió antes de ver el año de prueba.
F2 = make_scorer(fbeta_score, beta=2)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit  # noqa: E402

tab = nu.tabla_clasificador(df, cierres)
tr_c, te_c = tab[tab.index < nu.CORTE_PRUEBA], tab[tab.index >= nu.CORTE_PRUEBA]
Xtr, ytr_c, Xte, yte_c = tr_c[nu.COLUMNAS_X], tr_c["alto"], te_c[nu.COLUMNAS_X], te_c["alto"]
res["clasificador_datos"] = {"dias_entrenamiento": len(tr_c), "dias_prueba": len(te_c),
                             "tasa_alto_entrenamiento": float(ytr_c.mean()), "tasa_alto_prueba": float(yte_c.mean())}
cv = TimeSeriesSplit(n_splits=5)
resultados, ajustados = {}, {}
for nombre, (modelo, rejilla) in nu.modelos_candidatos().items():
    t0 = time.time()
    g = GridSearchCV(modelo, rejilla or {}, scoring=F2, cv=cv).fit(Xtr, ytr_c)
    best = g.best_estimator_
    p = best.predict(Xte)
    prob = best.predict_proba(Xte)[:, 1]
    tn, fp, fn, tp = confusion_matrix(yte_c, p, labels=[0, 1]).ravel()
    resultados[nombre] = {"f2_cv": float(g.best_score_), "f2": float(fbeta_score(yte_c, p, beta=2)), "mejores": {k: (v if not isinstance(v, np.generic) else v.item()) for k, v in g.best_params_.items()},
                          "precision": float(precision_score(yte_c, p, zero_division=0)), "recall": float(recall_score(yte_c, p)),
                          "f1": float(f1_score(yte_c, p)), "exactitud": float((p == yte_c).mean()), "auc": float(roc_auc_score(yte_c, prob)),
                          "matriz": [[int(tn), int(fp)], [int(fn), int(tp)]], "segundos": round(time.time() - t0, 2)}
    ajustados[nombre] = best
    print(nombre, {k: v for k, v in resultados[nombre].items() if k not in ("matriz",)})
# Regla simple que usaría Salomé sin modelo: "si dos días antes ya tengo 1 apartado y es fin de semana, va a ser día fuerte"
regla = ((Xte["apartados_enteros"] >= 1) & ((Xte["sab"] + Xte["dom"] + Xte["vie"]) > 0) | (Xte["apartados_enteros"] >= 2)).astype(int)
tn, fp, fn, tp = confusion_matrix(yte_c, regla, labels=[0, 1]).ravel()
resultados["Regla simple (apartados y fin de semana)"] = {"precision": float(precision_score(yte_c, regla, zero_division=0)),
                                             "recall": float(recall_score(yte_c, regla)), "f1": float(f1_score(yte_c, regla)),
                                             "f2": float(fbeta_score(yte_c, regla, beta=2)),
                                             "exactitud": float((regla == yte_c).mean()), "matriz": [[int(tn), int(fp)], [int(fn), int(tp)]]}
res["clasificador"] = resultados
# El ganador se elige por F2 en la validación cruzada (entrenamiento), no por el año de prueba
ganador = max((k for k in resultados if k in ajustados), key=lambda k: resultados[k]["f2_cv"])
res["clasificador_elegido"] = ganador
if hasattr(ajustados[ganador], "feature_importances_"):
    res["importancias"] = dict(zip(nu.COLUMNAS_X, np.round(ajustados[ganador].feature_importances_, 3).tolist()))

fig, axs = plt.subplots(1, 4, figsize=(13, 3.2))
for ax, nombre in zip(axs, list(ajustados)):
    mtx = np.array(resultados[nombre]["matriz"])
    ax.imshow(mtx, cmap="Oranges")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, mtx[i, j], ha="center", va="center", fontsize=12, color="black")
    ax.set_xticks([0, 1], ["normal", "fuerte"])
    ax.set_yticks([0, 1], ["normal", "fuerte"])
    ax.set_xlabel("Predicho")
    ax.set_title(f"{nombre}\nrecall {resultados[nombre]['recall']:.2f} · precisión {resultados[nombre]['precision']:.2f}", fontsize=9)
axs[0].set_ylabel("Real")
fig.suptitle("Matriz de confusión en el año de prueba (día fuerte = 2 o más pasteles enteros, decidido 2 días antes)", fontweight="bold", y=1.1)
fig.savefig(IMG / "e3_2_matrices.png")
plt.close(fig)

# ============================================================ 3. Versiones finales con toda la historia
t0 = time.time()
final_venta = nu.ajustar_sarima(y, orden, estacional)
final_ent = nu.ajustar_sarima(ye, orden, estacional)
modelo_c = nu.modelos_candidatos()[ganador][0].set_params(**resultados[ganador]["mejores"]).fit(tab[nu.COLUMNAS_X], tab["alto"])
res["segundos_reentreno_final"] = round(time.time() - t0, 2)
ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
artefactos = {}
# Del SARIMA se guarda la especificación y los parámetros: la API los aplica con el filtro de
# Kalman a los datos más recientes, sin reentrenar. Así el artefacto pesa unos cuantos bytes.
spec = lambda fit: {"orden": orden, "estacional": estacional, "parametros": fit.params.to_dict(),
                    "columna": None, "hasta": str(y.index.max().date())}
for nombre, obj in (("sarima_venta", spec(final_venta) | {"columna": "total"}),
                    ("sarima_enteros", spec(final_ent) | {"columna": "enteros"}),
                    ("clasificador_dia_fuerte", modelo_c)):
    archivo = MODELOS / f"{nombre}_v{VERSION}.pkl"
    with open(archivo, "wb") as fh:
        pickle.dump(obj, fh)
    artefactos[nombre] = {"archivo": archivo.name, "bytes": archivo.stat().st_size,
                          "sha256": hashlib.sha256(archivo.read_bytes()).hexdigest()[:16]}
registro = {"version": VERSION, "entrenado_en": ahora, "datos": res["datos"],
            "sarima": {"orden": list(orden), "estacional": list(estacional), "metricas_prueba": evaluacion[elegido]},
            "clasificador": {"modelo": ganador, "parametros": resultados[ganador]["mejores"], "umbral_enteros": 2,
                             "columnas": nu.COLUMNAS_X, "metricas_prueba": {k: resultados[ganador][k] for k in ("precision", "recall", "f1", "f2", "auc")},
                             "anticipo_dias": nu.ANTICIPO_DIAS},
            "artefactos": artefactos}
(MODELOS / "registro.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False))
(RAIZ / "docs/resultados_e3.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
print("elegidos:", elegido, "|", ganador)
