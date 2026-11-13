"""Pruebas del módulo de limpieza que corre dentro del worker.

Correr con:  python -m pytest -q tests/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "services" / "worker"))
sys.path.insert(0, str(RAIZ / "scripts"))

from limpieza import a_numero, cargar_catalogo, limpiar, normalizar_producto, validar_limpio  # noqa: E402

CAT = cargar_catalogo()
OFICIALES = sorted(CAT["producto"].unique())


def renglon(**cambios):
    base = {"pedido_id": "5001", "cliente_id": "C0100", "fecha_pedido": "2025-05-08", "hora_pedido": "20:15",
            "fecha_entrega": "2025-05-10", "producto": "Cheesecake frutos rojos entero",
            "categoria": "Pasteles enteros", "unidades": "1", "precio_unitario": "550", "total": "550",
            "canal": "WhatsApp", "entrega": "Domicilio", "metodo_pago": "Transferencia"}
    base.update(cambios)
    return base


def limpiar_filas(*filas):
    return limpiar(pd.DataFrame(list(filas)), CAT)


def test_duplicado_exacto_se_elimina():
    df, rep = limpiar_filas(renglon(), renglon())
    assert len(df) == 1 and rep.conteos["duplicados"] == 1


@pytest.mark.parametrize("escrito", ["cheesecake frutos rojos entero", "Cheescake frutos rojos entero",
                                     "Cheesecake frutos rojos entero ", "Cheesecake entero"])
def test_variantes_de_nombre(escrito):
    assert normalizar_producto(escrito, OFICIALES) == "Cheesecake frutos rojos entero"


def test_nombre_irreconocible_se_resuelve_por_precio_y_categoria():
    df, rep = limpiar_filas(renglon(producto="flan entero", fecha_pedido="2022-04-21", fecha_entrega="2022-04-22",
                                    precio_unitario="280", total="280"))
    assert df.loc[0, "producto"] == "Flan napolitano entero"
    assert rep.conteos["producto_por_precio_y_categoria"] == 1


def test_canal_abreviado():
    df, _ = limpiar_filas(renglon(canal="IG"), renglon(pedido_id="5002", canal="wa"))
    assert list(df["canal"]) == ["Instagram", "WhatsApp"]


@pytest.mark.parametrize("texto,esperado", [("2 pz", 2), ("dos", 2), ("1 entero", 1), ("3", 3), (4.0, 4)])
def test_unidades_como_texto(texto, esperado):
    assert a_numero(texto) == esperado


def test_fecha_en_formato_dia_mes_anio():
    df, rep = limpiar_filas(renglon(fecha_pedido="08/05/2025"))
    assert df.loc[0, "fecha_pedido"] == pd.Timestamp("2025-05-08")
    assert rep.conteos["fecha_formato"] == 1


def test_precio_vacio_usa_lista_vigente_en_la_fecha():
    df, _ = limpiar_filas(renglon(precio_unitario="", total="550"),
                          renglon(pedido_id="5002", fecha_pedido="2025-01-10", fecha_entrega="2025-01-12",
                                  precio_unitario=np.nan, total="520"))
    assert list(df["precio_unitario"]) == [520, 550]  # antes del 15 de enero sigue el precio de 2024


def test_unidades_vacias_se_reconstruyen_con_total():
    df, _ = limpiar_filas(renglon(producto="Rebanada cheesecake frutos rojos", categoria="Rebanadas",
                                  unidades="", precio_unitario="65", total="195"))
    assert df.loc[0, "unidades"] == 3


def test_unidades_negativas():
    df, rep = limpiar_filas(renglon(unidades="-1"))
    assert df.loc[0, "unidades"] == 1 and rep.conteos["unidades_negativas"] == 1


def test_cero_de_mas_es_atipico_y_se_reconstruye():
    df, rep = limpiar_filas(renglon(unidades="10", total="550"))
    assert df.loc[0, "unidades"] == 1 and rep.conteos["unidades_atipicas"] == 1


def test_pedido_grande_de_evento_no_se_toca():
    df, rep = limpiar_filas(renglon(producto="Cupcakes (docena)", categoria="Eventos", unidades="8",
                                    precio_unitario="360", total="2880"))
    assert df.loc[0, "unidades"] == 8 and rep.conteos["unidades_atipicas"] == 0


def test_total_inconsistente_se_recalcula():
    df, rep = limpiar_filas(renglon(total="505"))
    assert df.loc[0, "total"] == 550 and rep.conteos["total_inconsistente"] == 1


def test_anio_viejo_en_enero():
    df, _ = limpiar_filas(renglon(fecha_pedido="2026-01-03", fecha_entrega="2025-01-05"))
    assert df.loc[0, "fecha_entrega"] == pd.Timestamp("2026-01-05")


def test_fechas_al_reves():
    df, _ = limpiar_filas(renglon(fecha_pedido="2025-05-10", fecha_entrega="2025-05-08"))
    assert df.loc[0, "fecha_pedido"] == pd.Timestamp("2025-05-08")


def test_renglon_sin_producto_ni_precio_se_aparta():
    df, rep = limpiar_filas(renglon(), renglon(pedido_id="5002", producto="???", precio_unitario="", total=""))
    assert len(df) == 1 and len(rep.irrecuperables) == 1


def test_falta_columna_lanza_error():
    with pytest.raises(ValueError):
        limpiar(pd.DataFrame([renglon()]).drop(columns=["total"]), CAT)


def test_es_idempotente():
    df, _ = limpiar_filas(renglon(), renglon(pedido_id="5002", unidades="dos", total="1100"))
    otra, rep = limpiar(df.astype(str), CAT)
    pd.testing.assert_frame_equal(df, otra)
    assert sum(v for k, v in rep.conteos.items() if k != "hora_vacia_sin_imputar") == 0


def test_historial_completo():
    """El historial completo de pedidos sale limpio, sin renglones perdidos ni reglas rotas."""
    ruta = Path(__file__).resolve().parents[1] / "data/historial/pedidos_salome_2020_2026.csv"
    if not ruta.exists():
        pytest.skip("falta data/historial/pedidos_salome_2020_2026.csv")
    crudo = pd.read_csv(ruta, dtype=str)
    limpio, rep = limpiar(crudo, CAT)
    assert validar_limpio(limpio) == []
    assert rep.irrecuperables == []
    assert len(limpio) == len(crudo) - rep.conteos["duplicados"] - rep.conteos.get("duplicados_tras_normalizar", 0)
    assert limpio["pedido_id"].nunique() == crudo["pedido_id"].nunique()
