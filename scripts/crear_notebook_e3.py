"""Arma y ejecuta notebooks/E3_sarima_y_clasificador.ipynb (las cifras salen de scripts/entrenar_e3.py)."""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parents[1]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.cells = [
    md("# E3 · SARIMA y clasificador de días fuertes\nEl entrenamiento completo está en `scripts/entrenar_e3.py` "
       "(tarda alrededor de un minuto en CPU). Aquí se revisan sus resultados y se vuelve a ajustar el modelo elegido."),
    code("""import sys, json, pickle, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
RAIZ = Path.cwd().parent
sys.path += [str(RAIZ / "services/tablero"), str(RAIZ / "services/modelos")]
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import analitica as an, nucleo as nu
R = json.loads((RAIZ / "docs/resultados_e3.json").read_text())
df = an.preparar(pd.read_csv(RAIZ / "data/historial/pedidos_salome_clean.csv"))
y = nu.serie_sarima(df)
print(len(y), "días desde 2022;", int(y.isna().sum()), "cierres como faltantes;", int((y == 0).sum()), "días en cero")"""),
    md("## 1. Búsqueda de órdenes\np, q ∈ {0, 1, 2}, d = 0 (el ADF de E2 rechazó raíz unitaria en la serie diaria), "
       "P, D, Q ∈ {0, 1}, s = 7. 72 combinaciones ajustadas con 2022-01 a 2025-10."),
    code("""pd.DataFrame(R["sarima_top"])"""),
    code("""print("mejor sin diferencia estacional (D = 0):", R["sarima_mejor_D0"])"""),
    md("## 2. Evaluación fuera de muestra\nCada siete días del año de prueba (a partir del sábado 1 de noviembre de 2025) se pronostican los 7 días siguientes con lo que se sabía hasta ese día."),
    code("""pd.DataFrame(R["sarima_evaluacion"]).T[["MAE", "RMSE", "aic", "bic", "parametros", "cobertura_95"]]"""),
    md("## 3. El modelo elegido: menor BIC"),
    code("""ytr = y[y.index < nu.CORTE_PRUEBA]
fit = nu.ajustar_sarima(ytr, (0, 0, 0), (0, 1, 1, 7))
print(fit.summary().tables[1])"""),
    code("""from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.stats.diagnostic import acorr_ljungbox
r = fit.resid[14:].dropna()
fig, ax = plt.subplots(1, 2, figsize=(11, 3.2))
plot_acf(r, lags=21, ax=ax[0]); ax[1].hist(r, bins=30); plt.show()
acorr_ljungbox(r, lags=[7, 14], return_df=True)"""),
    md("El MA estacional sale en −0.9997: casi cancela la diferencia estacional. En la práctica el modelo aprendió "
       "un promedio estable por día de la semana y nada más, porque la venta de un día casi no dice nada del "
       "siguiente (ACF de rezago 1 = 0.08 en E2). Por eso empata con el promedio por día de la semana."),
    md("## 4. Pronóstico a 30 días con la versión final (toda la historia)"),
    code("""spec = pickle.loads((RAIZ / "models/sarima_venta_v1.pkl").read_bytes())
f = nu.pronostico(nu.aplicar_sarima(spec, y), 30)
ax = y[-56:].plot(style="o", ms=3, figsize=(11, 3.5), label="real")
f.pronostico.plot(ax=ax, label="pronóstico"); ax.fill_between(f.index, f.inferior, f.superior, alpha=.3); ax.legend(); plt.show()
f.head(10).round(0)"""),
    md("## 5. Clasificador: ¿2 o más pasteles enteros?, decidido dos días antes"),
    code("""print(R["clasificador_datos"])
pd.DataFrame(R["clasificador"]).T[["f2_cv", "precision", "recall", "f1", "f2", "auc"]].astype(float).round(3)"""),
    code("""from sklearn.tree import export_text
arbol = pickle.loads((RAIZ / "models/clasificador_dia_fuerte_v1.pkl").read_bytes())
print(export_text(arbol, feature_names=nu.COLUMNAS_X))"""),
    code("""json.loads((RAIZ / "models/registro.json").read_text())"""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(RAIZ / "notebooks")}}).execute()
nbf.write(nb, RAIZ / "notebooks/E3_sarima_y_clasificador.ipynb")
print("listo")
