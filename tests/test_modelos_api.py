"""Pruebas de la API de modelos con el CSV limpio local."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "data/historial/pedidos_salome_clean.csv"
pytestmark = pytest.mark.skipif(not CSV.exists(), reason="corre primero services/worker/limpieza.py")
os.environ.setdefault("FUENTE", "local")
os.environ.setdefault("RUTA_LOCAL", str(CSV))
sys.path[:0] = [str(RAIZ / "services/modelos"), str(RAIZ / "services/tablero")]


@pytest.fixture(scope="module")
def cliente():
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location("api_modelos", RAIZ / "services/modelos/app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return TestClient(mod.app)


def test_salud(cliente):
    assert cliente.get("/salud").json()["estado"] == "ok"


def test_pronostico_14_dias_con_banda(cliente):
    r = cliente.get("/pronostico", params={"dias": 14}).json()
    assert len(r["dias"]) == 14
    for d in r["dias"]:
        assert 0 <= d["inferior"] <= d["pronostico"] <= d["superior"] or not d["abierto"]
        if not d["abierto"]:
            assert d["pronostico"] == 0


def test_pronostico_enteros(cliente):
    r = cliente.get("/pronostico", params={"dias": 7, "serie": "enteros"}).json()
    assert r["unidad"] == "pasteles enteros" and len(r["dias"]) == 7


def test_pronostico_limites(cliente):
    assert cliente.get("/pronostico", params={"dias": 0}).status_code == 422
    assert cliente.get("/pronostico", params={"dias": 31}).status_code == 422
    assert cliente.get("/pronostico", params={"serie": "otra"}).status_code == 422


def test_clasificar_sabado_de_historia(cliente):
    r = cliente.get("/clasificar", params={"fecha": "2026-05-09"}).json()
    assert r["abierto"] and 0 <= r["probabilidad"] <= 1 and r["decidir_el"] == "2026-05-07"


def test_clasificar_lunes_cerrado(cliente):
    r = cliente.get("/clasificar", params={"fecha": "2026-10-26"}).json()
    assert r["abierto"] is False


def test_clasificar_fuera_de_rango(cliente):
    assert cliente.get("/clasificar", params={"fecha": "2027-06-01"}).status_code == 422


def test_modelo_registro(cliente):
    r = cliente.get("/modelo").json()
    assert r["version"] >= 1 and "sarima" in r and "clasificador" in r
