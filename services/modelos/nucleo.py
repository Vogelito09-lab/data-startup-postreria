"""Núcleo de los modelos de E3: SARIMA para el pronóstico y clasificador de días fuertes.

Lo usan el script de entrenamiento (scripts/entrenar_e3.py) y la API de modelos
(services/modelos/app.py). Trabaja sobre el CSV limpio o la vista v_lineas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import analitica as an

INICIO = "2022-01-01"
CORTE_PRUEBA = "2025-11-01"
ENTEROS = ["Pasteles enteros", "Eventos", "Temporada"]


# ---------------------------------------------------------------- serie para SARIMA
def serie_sarima(df: pd.DataFrame, columna: str = "total", cierres=None, hasta=None) -> pd.Series:
    """Venta diaria desde 2022. Los lunes quedan en cero (el patrón semanal los explica);
    los cierres que no son lunes (vacaciones, días sueltos) quedan como faltantes, porque
    ese cero no es demanda. SARIMAX maneja los faltantes con el filtro de Kalman."""
    datos = df if columna == "total" else df[df["categoria"].isin(ENTEROS)]
    s = an.serie_diaria(datos, "total" if columna == "total" else "unidades")
    fin = pd.Timestamp(hasta) if hasta is not None else df["fecha_entrega"].max()
    s = s.reindex(pd.date_range(INICIO, fin, freq="D"), fill_value=0.0)
    ab = an.abiertos(s.index, cierres)
    lunes_cerrado = (s.index.dayofweek == 0) & ~ab
    s[~ab & ~lunes_cerrado] = np.nan
    s.index.freq = "D"
    return s


def ajustar_sarima(y: pd.Series, orden=(0, 0, 1), estacional=(1, 1, 1, 7)):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    return SARIMAX(y, order=orden, seasonal_order=estacional, trend="n").fit(disp=False, maxiter=300)


def aplicar_sarima(spec: dict, y: pd.Series):
    """Aplica parámetros ya estimados a una serie (sin reentrenar): filtro de Kalman."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    m = SARIMAX(y, order=tuple(spec["orden"]), seasonal_order=tuple(spec["estacional"]), trend="n")
    return m.filter(pd.Series(spec["parametros"]).reindex(m.param_names).to_numpy())


def pronostico(res, dias: int = 14, cierres=None, nivel: float = 0.95) -> pd.DataFrame:
    """Pronóstico con banda de confianza. En días que Salomé no abre se fuerza a cero.
    La venta no puede ser negativa, así que el límite inferior se corta en cero."""
    f = res.get_forecast(steps=dias)
    ic = f.conf_int(alpha=1 - nivel)
    out = pd.DataFrame({"pronostico": f.predicted_mean, "inferior": ic.iloc[:, 0], "superior": ic.iloc[:, 1]})
    out[out < 0] = 0.0
    out.loc[~an.abiertos(out.index, cierres)] = 0.0
    out.index.name = "fecha"
    return out


# ---------------------------------------------------------------- clasificador
COLUMNAS_X = ["apartados_enteros", "apartados_pedidos", "enteros_hace_7", "media_enteros_28",
              "fecha_fuerte", "vispera", "quincena", "es_diciembre", "es_mayo",
              "vie", "sab", "dom", "mar_jue"]


ANTICIPO_DIAS = 2   # se decide dos días antes: el jueves para el sábado


def tabla_clasificador(df: pd.DataFrame, cierres=None, umbral: int = 2, hasta=None,
                       anticipo: int = ANTICIPO_DIAS) -> pd.DataFrame:
    """Una fila por día abierto. Objetivo: ¿ese día se entregan `umbral` o más pasteles enteros?
    Todo lo que entra como variable se conoce `anticipo` días antes, al cierre del día: el
    calendario, lo que ya está apartado para esa fecha y la historia hasta ese momento. Dos días
    porque el cheesecake reposa una noche y el queso crema se compra antes."""
    fin = pd.Timestamp(hasta) if hasta is not None else df["fecha_entrega"].max()
    idx = pd.date_range(INICIO, fin, freq="D")
    ent = df[df["categoria"].isin(ENTEROS)]
    enteros = ent.groupby("fecha_entrega")["unidades"].sum().reindex(idx, fill_value=0)
    limite = pd.Timedelta(days=anticipo)
    previo = ent[ent["fecha_pedido"] <= ent["fecha_entrega"] - limite]
    apartados = previo.groupby("fecha_entrega")["unidades"].sum().reindex(idx, fill_value=0)
    ped_prev = df[df["fecha_pedido"] <= df["fecha_entrega"] - limite].groupby("fecha_entrega")["pedido_id"].nunique()
    t = pd.DataFrame(index=idx)
    t["enteros"] = enteros
    t["alto"] = (enteros >= umbral).astype(int)
    t["apartados_enteros"] = apartados
    t["apartados_pedidos"] = ped_prev.reindex(idx, fill_value=0)
    t["enteros_hace_7"] = enteros.shift(7)
    t["media_enteros_28"] = enteros.shift(anticipo).rolling(28, min_periods=7).mean()
    md = list(zip(idx.month, idx.day))
    t["fecha_fuerte"] = [int(m in {(2, 14), (5, 10), (12, 24), (12, 31), (1, 6)}) for m in md]
    t["vispera"] = [int(m in {(2, 13), (5, 8), (5, 9), (12, 23), (12, 30), (1, 5)}) for m in md]
    t["quincena"] = an.es_quincena(idx).astype(int)
    t["es_diciembre"] = (idx.month == 12).astype(int)
    t["es_mayo"] = (idx.month == 5).astype(int)
    t["vie"] = (idx.dayofweek == 4).astype(int)
    t["sab"] = (idx.dayofweek == 5).astype(int)
    t["dom"] = (idx.dayofweek == 6).astype(int)
    t["mar_jue"] = idx.dayofweek.isin([1, 2, 3]).astype(int)
    t = t[an.abiertos(idx, cierres)].dropna()
    return t


def modelos_candidatos(semilla: int = 0) -> dict:
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier
    return {
        "Naive Bayes": (make_pipeline(StandardScaler(), GaussianNB()), {}),
        "SVM (RBF)": (make_pipeline(StandardScaler(), SVC(class_weight="balanced", probability=True, random_state=semilla)),
                      {"svc__C": [0.3, 1, 3], "svc__gamma": ["scale", 0.03]}),
        "KNN": (make_pipeline(StandardScaler(), KNeighborsClassifier()),
                {"kneighborsclassifier__n_neighbors": [5, 15, 31], "kneighborsclassifier__weights": ["uniform", "distance"]}),
        "Árbol de decisión": (DecisionTreeClassifier(class_weight="balanced", random_state=semilla),
                              {"max_depth": [2, 3, 4, 6], "min_samples_leaf": [5, 20]}),
    }
