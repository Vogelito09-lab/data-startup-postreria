"""E2 · Serie de tiempo y regresión lineal por mínimos cuadrados.

La regresión se resuelve a mano con la ecuación normal  β = (XᵀX)⁻¹ Xᵀ y  y se compara
contra scikit-learn. Lo usan el notebook de E2 y el tablero v2.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from analitica import es_quincena, serie_diaria

INICIO_MODELO = "2022-01-01"   # antes de 2022 el negocio estaba arrancando (otro régimen)
CORTE_PRUEBA = "2025-11-01"    # último año completo queda para evaluar
DIAS_COL = ["miercoles", "jueves", "viernes", "sabado", "domingo"]  # base: martes (y los pocos lunes abiertos)
MESES_COL = ["feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]  # base: enero


def dia_del_padre(anio: int) -> date:
    d = date(anio, 6, 1)
    return [d + timedelta(i) for i in range(30) if (d + timedelta(i)).weekday() == 6][2]


def fechas_fuertes(idx: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    md = list(zip(idx.month, idx.day))
    fuerte = np.array([m in {(2, 14), (5, 10), (12, 24), (12, 31), (1, 6)} for m in md])
    fuerte |= np.array([d.date() == dia_del_padre(d.year) for d in idx])
    vispera = np.array([m in {(2, 13), (5, 8), (5, 9), (12, 23), (12, 30), (1, 5)} for m in md])
    return fuerte, vispera


def dias_abiertos(serie: pd.Series, cierres: pd.Series | None = None) -> pd.Series:
    """Días en que Salomé trabajó: no es lunes normal, no está en su calendario de cierres."""
    idx = serie.index
    fuerte, vispera = fechas_fuertes(idx)
    abierto = (idx.dayofweek != 0) | fuerte | vispera
    abierto &= ~(((idx.month == 12) & (idx.day == 25)) | ((idx.month == 1) & (idx.day == 1)))
    if cierres is not None:
        abierto &= ~idx.isin(pd.to_datetime(cierres))
    return pd.Series(abierto, index=idx)


def matriz_diseno(idx: pd.DatetimeIndex, origen: str = INICIO_MODELO, cuadratica: bool = False) -> pd.DataFrame:
    """Columnas de X. La tendencia es lineal; con cuadratica=True se agrega t² (se probó y se descartó)."""
    t = (idx - pd.Timestamp(origen)).days / 365.25
    X = pd.DataFrame(index=idx)
    X["intercepto"] = 1.0
    X["t_anios"] = t
    if cuadratica:
        X["t_anios2"] = t ** 2
    for i, nombre in zip([2, 3, 4, 5, 6], DIAS_COL):
        X[nombre] = (idx.dayofweek == i).astype(float)
    for m, nombre in zip(range(2, 13), MESES_COL):
        X[nombre] = (idx.month == m).astype(float)
    X["quincena"] = es_quincena(idx).astype(float)
    fuerte, vispera = fechas_fuertes(idx)
    X["fecha_fuerte"] = fuerte.astype(float)
    X["vispera_fuerte"] = vispera.astype(float)
    return X


def mco(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Mínimos cuadrados con la ecuación normal, tal cual se ve en clase."""
    XtX = X.T @ X
    return np.linalg.inv(XtX) @ X.T @ y


def metricas(y: np.ndarray, yhat: np.ndarray) -> dict:
    e = y - yhat
    mse = float(np.mean(e ** 2))
    return {"MSE": mse, "RMSE": float(np.sqrt(mse)), "MAE": float(np.mean(np.abs(e))),
            "R2": float(1 - np.sum(e ** 2) / np.sum((y - y.mean()) ** 2))}


def datos_modelo(df: pd.DataFrame, cierres=None) -> pd.DataFrame:
    s = serie_diaria(df)
    abierto = dias_abiertos(s, cierres)
    d = pd.DataFrame({"venta": s, "abierto": abierto})
    return d[(d.index >= INICIO_MODELO) & d.abierto]


def ajustar(df: pd.DataFrame, cierres=None, cuadratica: bool = False) -> dict:
    d = datos_modelo(df, cierres)
    X = matriz_diseno(d.index, cuadratica=cuadratica)
    tr = d.index < CORTE_PRUEBA
    Xtr, ytr = X[tr].to_numpy(), d.venta[tr].to_numpy()
    Xte, yte = X[~tr].to_numpy(), d.venta[~tr].to_numpy()
    beta = mco(Xtr, ytr)

    from sklearn.linear_model import LinearRegression
    sk = LinearRegression(fit_intercept=False).fit(Xtr, ytr)
    pred_tr, pred_te = Xtr @ beta, Xte @ beta
    res = {
        "beta": pd.Series(beta, index=X.columns),
        "beta_sklearn": pd.Series(sk.coef_, index=X.columns),
        "dif_max_sklearn": float(np.max(np.abs(beta - sk.coef_))),
        "dif_pred_sklearn": float(np.max(np.abs(pred_te - sk.predict(Xte)))),
        "condicion_XtX": float(np.linalg.cond(Xtr.T @ Xtr)),
        "metricas_entrenamiento": metricas(ytr, pred_tr),
        "metricas_prueba": metricas(yte, pred_te),
        "metricas_sklearn_prueba": metricas(yte, sk.predict(Xte)),
        "fechas_tr": d.index[tr], "fechas_te": d.index[~tr],
        "y_tr": ytr, "y_te": yte, "pred_tr": pred_tr, "pred_te": pred_te,
        "residuos": ytr - pred_tr, "n_tr": int(tr.sum()), "n_te": int((~tr).sum()),
    }
    # Línea base para saber si el modelo aporta algo: el mismo día de la semana pasada
    s = serie_diaria(df)
    ingenuo = s.shift(7).reindex(d.index[~tr]).to_numpy()
    res["metricas_ingenuo_prueba"] = metricas(yte, ingenuo)
    return res


def tendencia(res: dict, idx: pd.DatetimeIndex) -> pd.Series:
    """Parte de la regresión que solo depende del tiempo, más el efecto promedio del calendario."""
    cuad = "t_anios2" in res["beta"].index
    X = matriz_diseno(idx, cuadratica=cuad)
    b = res["beta"]
    tiempo = [c for c in ("intercepto", "t_anios", "t_anios2") if c in X.columns]
    resto = [c for c in X.columns if c not in tiempo]
    nivel = (matriz_diseno(res["fechas_tr"], cuadratica=cuad)[resto] @ b[resto]).mean()
    return pd.Series(X[tiempo].to_numpy() @ b[tiempo].to_numpy() + nivel, index=idx)


def predecir(res: dict, idx: pd.DatetimeIndex) -> pd.Series:
    X = matriz_diseno(idx, cuadratica="t_anios2" in res["beta"].index)
    return pd.Series(X.to_numpy() @ res["beta"].to_numpy(), index=idx)


def descomposicion(df: pd.DataFrame, periodo: int = 7, desde: str = INICIO_MODELO):
    from statsmodels.tsa.seasonal import STL
    s = serie_diaria(df)
    s = s[s.index >= desde]
    return STL(s, period=periodo, robust=True).fit()


def descomposicion_mensual(df: pd.DataFrame):
    from statsmodels.tsa.seasonal import seasonal_decompose
    s = df.groupby(pd.to_datetime(df["fecha_entrega"]).dt.to_period("M"))["total"].sum()
    s = s[(s.index >= "2020-03") & (s.index <= "2026-10")]
    s.index = s.index.to_timestamp()
    return seasonal_decompose(s, model="multiplicative", period=12)


def adf(serie: pd.Series, regresion: str = "c") -> dict:
    from statsmodels.tsa.stattools import adfuller
    est, p, lags, n, crit, _ = adfuller(serie.dropna(), regression=regresion, autolag="AIC")
    return {"estadistico": float(est), "p_valor": float(p), "rezagos": int(lags), "n": int(n),
            "critico_5": float(crit["5%"]), "estacionaria_5": bool(p < 0.05)}
