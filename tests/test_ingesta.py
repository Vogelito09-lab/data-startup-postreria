"""Pruebas de la validación de entrada de la API (sin tocar AWS ni la base)."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("api_ingesta", Path(__file__).resolve().parents[1] / "services/ingesta/app.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["api_ingesta"] = _mod  # pydantic resuelve los modelos de respuesta por nombre de módulo
_spec.loader.exec_module(_mod)
COLUMNAS, LineaPedido, _validar_csv = _mod.COLUMNAS, _mod.LineaPedido, _mod._validar_csv

ENC = ",".join(COLUMNAS)
FILA = "8001,C0042,2026-11-03,20:41,2026-11-05,Cheesecake frutos rojos entero,Pasteles enteros,1,590,590,WhatsApp,Domicilio,Transferencia"


def codigo(contenido: bytes) -> int:
    with pytest.raises(HTTPException) as e:
        _validar_csv(contenido)
    return e.value.status_code


def test_csv_valido_cuenta_renglones():
    assert _validar_csv(f"{ENC}\n{FILA}\n{FILA.replace('8001', '8002')}\n".encode()) == 2


def test_acepta_bom_de_excel():
    assert _validar_csv(("﻿" + f"{ENC}\n{FILA}\n").encode("utf-8")) == 1


def test_vacio():
    assert codigo(b"") == 400


def test_sin_renglones():
    assert codigo(f"{ENC}\n".encode()) == 400


def test_faltan_columnas():
    assert codigo(b"pedido_id,fecha\n1,2026-01-01\n") == 422


def test_renglon_cortado():
    assert codigo(f"{ENC}\n8001,C0042,2026-11-03\n".encode()) == 422


def test_pedido_id_no_numerico():
    assert codigo(f"{ENC}\n{FILA.replace('8001', 'abc')}\n".encode()) == 422


def test_no_utf8():
    assert codigo(f"{ENC}\n{FILA.replace('limón', 'lim')}\n".encode("utf-8").replace(b"Cheesecake", b"Cheesecak\xe9")) == 400


def test_json_rechaza_nombre_de_cliente():
    with pytest.raises(Exception):
        LineaPedido(pedido_id=1, cliente_id="Juan Pérez", fecha_pedido="2026-11-03", fecha_entrega="2026-11-04",
                    producto="Rosca de Reyes", categoria="Temporada", unidades=1, canal="WhatsApp",
                    entrega="Recoge", metodo_pago="Efectivo")


def test_llave_obligatoria_cuando_hay_token(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(_mod, "TOKEN", "secreto")
    c = TestClient(_mod.app)
    datos = {"archivo": ("p.csv", f"{ENC}\n{FILA}\n".encode(), "text/csv")}
    assert c.post("/pedidos/csv", files=datos).status_code == 401
    assert c.post("/pedidos/csv", files=datos, headers={"X-Api-Key": "otra"}).status_code == 401
    monkeypatch.setattr(_mod, "_registrar", lambda contenido, n, origen: {"carga_id": "x", "estado": "recibida",
                                                                         "s3_key": "raw/x", "renglones": n, "mensaje": "ok"})
    assert c.post("/pedidos/csv", files=datos, headers={"X-Api-Key": "secreto"}).status_code == 202
