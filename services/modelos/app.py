"""API de modelos de Salomé (FastAPI).

    GET /pronostico?dias=14&serie=venta     venta (o pasteles enteros) por día con banda de 95%
    GET /clasificar?fecha=2026-11-07        ¿ese día se entregarán 2 o más pasteles enteros?
    GET /modelo                             versión, métricas y huellas de los artefactos
    GET /salud                              revisión de vida (la usan ECS y Kubernetes)

Los modelos se cargan una vez de MODELOS_DIR (models/registro.json + *.pkl). Los datos se
leen de la misma fuente que el tablero (FUENTE=postgres|s3|local) con caché de 60 segundos,
así el pronóstico siempre parte del último pedido registrado sin reentrenar.
"""
from __future__ import annotations

import json
import os
import pickle
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

import analitica as an
import fuente
import nucleo as nu

# El valor por defecto se calcula solo fuera del contenedor: en /app/app.py no existe parents[2].
MODELOS_DIR = Path(os.environ["MODELOS_DIR"]) if "MODELOS_DIR" in os.environ else Path(__file__).resolve().parents[2] / "models"
CACHE_SEGUNDOS = int(os.getenv("CACHE_SEGUNDOS", "60"))
# El pronóstico solo cambia cuando cambian los datos: se guarda por versión de datos.
# CACHE_PRONOSTICO=0 lo apaga (así se midió la prueba de carga sin caché).
CACHE_PRONOSTICO = os.getenv("CACHE_PRONOSTICO", "1") == "1"

app = FastAPI(title="Salomé · API de modelos", version="3.0.0",
              description="Pronóstico SARIMA de la venta diaria y clasificador de días fuertes, servidos desde la nube.")

_registro = json.loads((MODELOS_DIR / "registro.json").read_text(encoding="utf-8"))
_art = {k: pickle.loads((MODELOS_DIR / v["archivo"]).read_bytes()) for k, v in _registro["artefactos"].items()}
_lock = threading.Lock()
_cache: dict = {"t": 0.0, "df": None}
_respuestas: dict = {}


def datos() -> pd.DataFrame:
    with _lock:
        if _cache["df"] is None or time.time() - _cache["t"] > CACHE_SEGUNDOS:
            nuevo = an.preparar(fuente.leer_pedidos())
            if _cache["df"] is None or len(nuevo) != len(_cache["df"]) or nuevo["fecha_pedido"].max() != _cache["df"]["fecha_pedido"].max():
                _respuestas.clear()  # llegaron pedidos: lo calculado antes ya no sirve
            _cache["df"] = nuevo
            _cache["t"] = time.time()
        return _cache["df"]


@app.get("/salud")
def salud():
    return {"estado": "ok", "version_modelos": _registro["version"]}


@app.get("/modelo")
def modelo():
    return _registro


@app.get("/pronostico")
def pronosticar(dias: int = Query(14, ge=1, le=30, description="Días a pronosticar (1 a 30)"),
                serie: Literal["venta", "enteros"] = "venta"):
    df = datos()
    clave = ("pronostico", dias, serie)
    if CACHE_PRONOSTICO and clave in _respuestas:
        return _respuestas[clave]
    spec = _art["sarima_venta" if serie == "venta" else "sarima_enteros"]
    y = nu.serie_sarima(df, "total" if serie == "venta" else "enteros")
    f = nu.pronostico(nu.aplicar_sarima(spec, y), dias)
    respuesta = {"serie": serie, "unidad": "MXN" if serie == "venta" else "pasteles enteros", "nivel": 0.95,
            "datos_hasta": str(y.index.max().date()), "modelo": "SARIMA({},{},{})({},{},{}){}".format(*spec["orden"], *spec["estacional"]),
            "dias": [{"fecha": str(i.date()), "pronostico": round(float(r.pronostico), 2),
                      "inferior": round(float(r.inferior), 2), "superior": round(float(r.superior), 2),
                      "abierto": bool(an.abiertos(pd.DatetimeIndex([i]))[0])} for i, r in f.iterrows()]}
    if CACHE_PRONOSTICO:
        _respuestas[clave] = respuesta
    return respuesta


@app.get("/clasificar")
def clasificar(fecha: date | None = Query(None, description="Día de entrega; por omisión, dos días después del último dato")):
    df = datos()
    ultimo = df["fecha_entrega"].max().date()
    fecha = fecha or (ultimo + timedelta(days=nu.ANTICIPO_DIAS))
    if fecha > ultimo + timedelta(days=14):
        raise HTTPException(422, f"Solo se clasifica hasta 14 días después del último dato ({ultimo}).")
    if fecha < date.fromisoformat(nu.INICIO):
        raise HTTPException(422, f"No hay datos antes de {nu.INICIO}.")
    if not an.abiertos(pd.DatetimeIndex([pd.Timestamp(fecha)]))[0]:
        return {"fecha": str(fecha), "abierto": False, "dia_fuerte": False, "probabilidad": 0.0,
                "mensaje": "Ese día no hay entregas (descanso o cierre registrado)."}
    clave = ("clasificar", fecha)
    if CACHE_PRONOSTICO and clave in _respuestas:
        return _respuestas[clave]
    tab = nu.tabla_clasificador(df, hasta=fecha)
    fila = tab.loc[[pd.Timestamp(fecha)], nu.COLUMNAS_X]
    m = _art["clasificador_dia_fuerte"]
    prob = float(m.predict_proba(fila)[0, 1])
    clase = bool(m.predict(fila)[0])
    respuesta = {"fecha": str(fecha), "abierto": True, "dia_fuerte": clase, "probabilidad": round(prob, 3),
            "apartados_enteros": int(fila.iloc[0]["apartados_enteros"]), "apartados_pedidos": int(fila.iloc[0]["apartados_pedidos"]),
            "decidir_el": str(fecha - timedelta(days=nu.ANTICIPO_DIAS)),
            "mensaje": ("Prepara base para 2 o más pasteles enteros." if clase
                        else "Día normal: con 1 pastel entero listo alcanza.")}
    if CACHE_PRONOSTICO:
        _respuestas[clave] = respuesta
    return respuesta
