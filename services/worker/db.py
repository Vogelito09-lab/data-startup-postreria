"""Escritura en PostgreSQL. Todo lo de una carga va en una sola transacción:
si algo falla, no queda la mitad de los pedidos escrita."""
from __future__ import annotations

import json
import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


def conectar(url: str | None = None):
    return psycopg2.connect(url or os.environ["DATABASE_URL"])


def asegurar_carga(conn, carga_id: str, s3_key: str) -> None:
    """Si la ingesta no alcanzó a registrar la carga, el worker la registra."""
    with conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cargas (carga_id, s3_key) VALUES (%s, %s)
                       ON CONFLICT (carga_id) DO NOTHING""", (carga_id, s3_key))


def marcar(conn, carga_id: str, estado: str, **campos) -> None:
    sets = ["estado = %s"]
    vals = [estado]
    for k, v in campos.items():
        sets.append(f"{k} = %s")
        vals.append(json.dumps(v, ensure_ascii=False, default=str) if k == "reporte" else v)
    with conn, conn.cursor() as cur:
        cur.execute(f"UPDATE cargas SET {', '.join(sets)} WHERE carga_id = %s", [*vals, carga_id])


def guardar_pedidos(conn, df: pd.DataFrame, carga_id: str) -> int:
    """Inserta o actualiza los pedidos de la carga. Reenviar el mismo archivo no duplica nada."""
    if df.empty:
        return 0
    with conn, conn.cursor() as cur:
        prods = df[["producto", "categoria"]].drop_duplicates()
        execute_values(cur, """INSERT INTO productos (nombre, categoria) VALUES %s
                               ON CONFLICT (nombre) DO NOTHING""", list(prods.itertuples(index=False)))
        cur.execute("SELECT nombre, producto_id FROM productos")
        ids = dict(cur.fetchall())

        cli = df.groupby("cliente_id")["fecha_pedido"].min().reset_index()
        execute_values(cur, """INSERT INTO clientes (cliente_id, primer_pedido) VALUES %s
                               ON CONFLICT (cliente_id) DO UPDATE
                               SET primer_pedido = LEAST(clientes.primer_pedido, EXCLUDED.primer_pedido)""",
                       [(r.cliente_id, r.fecha_pedido.date()) for r in cli.itertuples()])

        ped = df.drop_duplicates("pedido_id")
        filas = [(int(r.pedido_id), r.cliente_id, r.fecha_pedido.date(),
                  None if pd.isna(r.hora_pedido) else r.hora_pedido, r.fecha_entrega.date(),
                  r.canal, r.entrega, r.metodo_pago, carga_id) for r in ped.itertuples()]
        execute_values(cur, """INSERT INTO pedidos (pedido_id, cliente_id, fecha_pedido, hora_pedido, fecha_entrega,
                                                    canal, entrega, metodo_pago, carga_id) VALUES %s
                               ON CONFLICT (pedido_id) DO UPDATE SET
                                 cliente_id = EXCLUDED.cliente_id, fecha_pedido = EXCLUDED.fecha_pedido,
                                 hora_pedido = EXCLUDED.hora_pedido, fecha_entrega = EXCLUDED.fecha_entrega,
                                 canal = EXCLUDED.canal, entrega = EXCLUDED.entrega,
                                 metodo_pago = EXCLUDED.metodo_pago, carga_id = EXCLUDED.carga_id""",
                       filas, page_size=1000)
        # La versión más nueva de un pedido reemplaza sus renglones anteriores
        cur.execute("DELETE FROM lineas_pedido WHERE pedido_id = ANY(%s)", ([int(x) for x in ped.pedido_id],))
        lineas = [(int(r.pedido_id), ids[r.producto], int(r.unidades), float(r.precio_unitario), float(r.total))
                  for r in df.itertuples()]
        execute_values(cur, """INSERT INTO lineas_pedido (pedido_id, producto_id, unidades, precio_unitario, total)
                               VALUES %s""", lineas, page_size=2000)
    return len(lineas)
