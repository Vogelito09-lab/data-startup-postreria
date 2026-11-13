"""Arma y ejecuta los notebooks de E1 y E2 (quedan con sus salidas en notebooks/)."""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parents[1]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

INICIO = code("""import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
RAIZ = Path.cwd().parent
sys.path += [str(RAIZ / "services/tablero"), str(RAIZ / "services/worker")]
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import analitica as an, modelos_e2 as m2
from limpieza import limpiar, validar_limpio
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")""")

e1 = nbf.v4.new_notebook()
e1.cells = [
    md("# E1 · Limpieza y hallazgos del tablero\nPedidos de Salomé del 5 de febrero de 2020 al 24 de octubre de 2026."),
    INICIO,
    md("## 1. Datos crudos\nAsí llegan a `raw/`: una fila por producto dentro de cada pedido, con los errores de copiar los chats a mano."),
    code("""crudo = pd.read_csv(RAIZ / "data/historial/historial_hasta_2026-10-24.csv", dtype=str)
print(crudo.shape)
crudo.sample(8, random_state=3)"""),
    md("## 2. Limpieza\n`limpiar()` es el mismo módulo que corre el worker. El reporte dice cuántos renglones se tocaron por tipo de error."),
    code("""limpio, rep = limpiar(crudo)
r = rep.como_dict()
print(r["crudos"], "->", r["limpios"], "renglones; irrecuperables:", r["irrecuperables"])
pd.Series(r["conteos"]).loc[lambda s: s > 0].sort_values(ascending=False).to_frame("renglones")"""),
    code("""print("validación del archivo limpio:", validar_limpio(limpio) or "sin problemas")"""),
    md("## 3. Indicadores"),
    code("""df = an.preparar(limpio)
k = an.kpis(df)
{c: k[c] for c in ["ventas", "pedidos", "ticket", "ticket_mediana", "estrella", "estrella_pct", "ult7", "ant7", "var7"]}"""),
    md("## 4. Títulos de las seis gráficas (se calculan de los datos)"),
    code("""t = an.titulos(df)
for c in ["lineas", "histograma", "calor", "dispersion", "espectro", "barras", "dia_semana"]:
    print(f"{c:11s}", t[c])"""),
    md("## 5. Análisis espectral\nSerie diaria por fecha de entrega con ceros en los días sin entregas, menos su media móvil de 28 días; "
       "`numpy.fft.rfft`, potencia |X(f)|² y periodo T = 1/f."),
    code("""esp = an.espectro(an.serie_diaria(df))
an.picos(esp, n=6)"""),
    code("""pk = an.picos(esp)
print("potencia cerca de 15.2 días:", round(an.potencia_cerca(esp, 15.2) / pk.potencia.iloc[0], 3), "de la semanal")
print("potencia cerca de 30.4 días:", round(an.potencia_cerca(esp, 30.4) / pk.potencia.iloc[0], 3), "de la semanal")
an.prueba_quincena(df)"""),
    md("La FFT encuentra la semana (7 días) y sus armónicos (3.5 y 2.33 días, que salen porque la semana no tiene forma de "
       "seno: el lunes vale cero y el sábado sube de golpe). La quincena no sobresale en el espectro porque su efecto es "
       "pequeño frente al ruido diario y porque no es exactamente periódica (los meses duran de 28 a 31 días). Comparando "
       "directamente quincena contra días normales del mismo día de la semana sale una diferencia chica que no es "
       "significativa: con estos datos no se puede confirmar el efecto de la quincena."),
    md("## 6. Recomendaciones"),
    code("""for x in an.recomendaciones(df):
    print(x["titulo"], "\\n ", x["texto"], "\\n")"""),
]

e2 = nbf.v4.new_notebook()
e2.cells = [
    md("# E2 · Serie de tiempo y regresión por mínimos cuadrados\nVenta diaria de Salomé por fecha de entrega. "
       "Incluye la semana del 25 al 31 de octubre de 2026 que entró por la tubería."),
    INICIO,
    code("""df = an.preparar(pd.read_csv(RAIZ / "data/historial/pedidos_salome_clean.csv"))
cierres = pd.read_csv(RAIZ / "services/worker/referencia/calendario_cierres.csv")["fecha"]
s = an.serie_diaria(df)
s22 = s[s.index >= m2.INICIO_MODELO]
print(s.index.min().date(), "a", s.index.max().date(), len(s), "días;", "desde 2022:", len(s22))"""),
    md("## 1. Descomposición\nSTL con periodo 7 sobre la venta diaria desde 2022 (antes el negocio estaba arrancando) y "
       "descomposición clásica multiplicativa con periodo 12 sobre la venta mensual."),
    code("""stl = m2.descomposicion(df)
fig = stl.plot(); fig.set_size_inches(10, 7); plt.show()
partes = {"tendencia": stl.trend.var(), "estacional": stl.seasonal.var(), "residuo": stl.resid.var()}
{k: round(v / stl.observed.var(), 3) for k, v in partes.items()}"""),
    code("""stl.seasonal.groupby(stl.seasonal.index.dayofweek).mean().rename(dict(enumerate(an.DIAS))).round(0)"""),
    code("""dm = m2.descomposicion_mensual(df)
fig = dm.plot(); fig.set_size_inches(10, 6); plt.show()
dm.seasonal.iloc[:12].sort_index(key=lambda i: i.month).rename(lambda i: an.MESES[i.month - 1]).round(3)"""),
    md("## 2. Estacionariedad (Dickey-Fuller aumentada)\nH0: la serie tiene raíz unitaria (no es estacionaria)."),
    code("""mens = df.groupby(df.fecha_entrega.dt.to_period("M")).total.sum()
mens = mens[(mens.index >= "2020-03") & (mens.index <= "2026-10")].astype(float)
pruebas = {"diaria desde 2022 (constante)": m2.adf(s22), "diaria desde 2022 (constante y tendencia)": m2.adf(s22, "ct"),
           "diaria 2020-2026 (constante y tendencia)": m2.adf(s, "ct"), "diaria, diferencia de 7 días": m2.adf(s22.diff(7)),
           "mensual 2020-2026": m2.adf(mens), "mensual, primera diferencia": m2.adf(mens.diff())}
pd.DataFrame(pruebas).T[["estadistico", "critico_5", "p_valor", "rezagos", "estacionaria_5"]]"""),
    md("## 3. ACF y PACF"),
    code("""from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import acf, pacf
fig, ax = plt.subplots(1, 2, figsize=(12, 3.5))
plot_acf(s22, lags=28, ax=ax[0]); plot_pacf(s22, lags=28, ax=ax[1], method="ywm"); plt.show()
pd.DataFrame({"ACF": acf(s22, nlags=28), "PACF": pacf(s22, nlags=28)}).iloc[[1, 2, 6, 7, 8, 14, 21, 28]].round(3)"""),
    md("## 4. Regresión lineal por mínimos cuadrados, a mano\n"
       "y = venta del día (solo días que Salomé abrió). X = intercepto, tendencia en años, día de la semana (base martes), "
       "mes (base enero), quincena, fecha fuerte y víspera de fecha fuerte. Entrenamiento: 2022-01-01 a 2025-10-31; "
       "prueba: 2025-11-01 a 2026-10-31.\n\nβ = (XᵀX)⁻¹ Xᵀ y"),
    code("""d = m2.datos_modelo(df, cierres)
X = m2.matriz_diseno(d.index)
tr = d.index < m2.CORTE_PRUEBA
Xtr, ytr, Xte, yte = X[tr].to_numpy(), d.venta[tr].to_numpy(), X[~tr].to_numpy(), d.venta[~tr].to_numpy()
XtX = Xtr.T @ Xtr
beta = np.linalg.inv(XtX) @ Xtr.T @ ytr          # la ecuación normal, tal cual
print("X:", Xtr.shape, " número de condición de XᵀX:", round(np.linalg.cond(XtX)))"""),
    md("Errores estándar con la fórmula clásica: σ̂² = SSE / (n − p) y Var(β̂) = σ̂² (XᵀX)⁻¹."),
    code("""from scipy import stats
e = ytr - Xtr @ beta
n, p = Xtr.shape
sigma2 = e @ e / (n - p)
ee = np.sqrt(np.diag(sigma2 * np.linalg.inv(XtX)))
tabla = pd.DataFrame({"beta": beta, "error_est": ee, "t": beta / ee}, index=X.columns)
tabla["p_valor"] = 2 * stats.t.sf(np.abs(tabla.t), n - p)
tabla"""),
    md("### Comparación contra scikit-learn"),
    code("""from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
sk = LinearRegression(fit_intercept=False).fit(Xtr, ytr)
print("diferencia máxima entre coeficientes:", np.abs(beta - sk.coef_).max())
print("diferencia máxima entre predicciones de prueba:", np.abs(Xte @ beta - sk.predict(Xte)).max())"""),
    code("""filas = {}
for nombre, y, yhat in [("entrenamiento (a mano)", ytr, Xtr @ beta), ("prueba (a mano)", yte, Xte @ beta),
                        ("prueba (scikit-learn)", yte, sk.predict(Xte))]:
    filas[nombre] = m2.metricas(y, yhat)
ingenuo = s.shift(7).reindex(d.index[~tr]).to_numpy()
filas["prueba: ingenuo estacional"] = m2.metricas(yte, ingenuo)
filas["prueba: con t² (descartado)"] = m2.ajustar(df, cierres, cuadratica=True)["metricas_prueba"]
pd.DataFrame(filas).T"""),
    code("""# sklearn.metrics da lo mismo que nuestras fórmulas
yhat = Xte @ beta
mean_squared_error(yte, yhat), np.sqrt(mean_squared_error(yte, yhat)), mean_absolute_error(yte, yhat), r2_score(yte, yhat)"""),
    md("### Lineal contra cuadrática: se decide con un año de validación dentro del entrenamiento"),
    code("""va, tr2 = (d.index >= "2025-01-01") & (d.index < m2.CORTE_PRUEBA), d.index < "2025-01-01"
for cuad in (False, True):
    Xv = m2.matriz_diseno(d.index, cuadratica=cuad)
    b = m2.mco(Xv[tr2].to_numpy(), d.venta[tr2].to_numpy())
    print("cuadrática" if cuad else "lineal    ", {k: round(v, 3) for k, v in m2.metricas(d.venta[va].to_numpy(), Xv[va].to_numpy() @ b).items()})
r_q = m2.ajustar(df, cierres, cuadratica=True)
print("sesgo en prueba (real − predicho): lineal", round(np.mean(yte - Xte @ beta)), " cuadrática", round(np.mean(r_q["y_te"] - r_q["pred_te"])))"""),
    md("## 5. Análisis de residuos"),
    code("""from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.graphics.gofplots import qqplot
fig, ax = plt.subplots(2, 2, figsize=(11, 7))
ax[0, 0].scatter(Xtr @ beta, e, s=5, alpha=.4); ax[0, 0].axhline(0, color="k"); ax[0, 0].set_title("residuo vs ajuste")
ax[0, 1].hist(e, bins=int(np.ceil(np.log2(len(e)) + 1))); ax[0, 1].set_title("histograma")
qqplot(e, line="s", ax=ax[1, 0], markersize=2); plot_acf(e, lags=21, ax=ax[1, 1]); plt.tight_layout(); plt.show()
{"media": e.mean(), "asimetría": stats.skew(e), "curtosis exceso": stats.kurtosis(e), "Durbin-Watson": durbin_watson(e),
 "Breusch-Pagan p": het_breuschpagan(e, Xtr)[1], "Shapiro p": stats.shapiro(e).pvalue,
 "corr(|e|, ajuste)": np.corrcoef(np.abs(e), Xtr @ beta)[0, 1]}"""),
    md("## 6. Lo que esto deja para E3\n"
       "La ACF con picos en 7, 14, 21 y 28 que bajan despacio y la PACF con picos estacionales piden un SARIMA con "
       "periodo 7 y diferencia estacional (D = 1). El ADF diario no obliga a diferenciar la parte no estacional (d = 0 "
       "o 1 se decide por AIC). La regresión queda como línea base explicable: le gana al ingenuo estacional, pero con poco "
       "más de un pedido diario explica muy poco de la variación de un día, y sus residuos crecen en los días grandes. "
       "En E3 conviene probar también la escala semanal."),
]

for nb, nombre in ((e1, "E1_limpieza_y_hallazgos.ipynb"), (e2, "E2_series_y_regresion.ipynb")):
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(RAIZ / "notebooks")}}).execute()
    nbf.write(nb, RAIZ / "notebooks" / nombre)
    print("listo", nombre)
