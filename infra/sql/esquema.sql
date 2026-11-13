-- Esquema de la base de datos de Salomé (PostgreSQL 16, Amazon RDS db.t4g.micro)
-- Se aplica una vez con el usuario maestro:  psql "$DATABASE_URL_ADMIN" -f infra/sql/esquema.sql
-- Es idempotente: se puede correr de nuevo sin romper nada.

CREATE TABLE IF NOT EXISTS productos (
    producto_id  SERIAL PRIMARY KEY,
    nombre       TEXT NOT NULL UNIQUE,
    categoria    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
    cliente_id     TEXT PRIMARY KEY,              -- identificador anónimo (C0001); nunca nombre ni teléfono
    primer_pedido  DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS cargas (
    carga_id          UUID PRIMARY KEY,
    s3_key            TEXT NOT NULL,
    origen            TEXT NOT NULL DEFAULT 'csv' CHECK (origen IN ('csv', 'json')),
    recibida_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    procesada_en      TIMESTAMPTZ,
    estado            TEXT NOT NULL DEFAULT 'recibida'
                      CHECK (estado IN ('recibida', 'procesando', 'procesada', 'error')),
    intentos          INT NOT NULL DEFAULT 0,
    registros_crudos  INT,
    registros_limpios INT,
    reporte           JSONB,
    error             TEXT
);

CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id      INT PRIMARY KEY,
    cliente_id     TEXT REFERENCES clientes (cliente_id),
    fecha_pedido   DATE NOT NULL,
    hora_pedido    TIME,                          -- puede faltar: no se inventa
    fecha_entrega  DATE NOT NULL,
    canal          TEXT CHECK (canal IN ('WhatsApp', 'Instagram', 'Facebook')),
    entrega        TEXT CHECK (entrega IN ('Domicilio', 'Recoge')),
    metodo_pago    TEXT CHECK (metodo_pago IN ('Efectivo', 'Transferencia', 'Tarjeta')),
    carga_id       UUID REFERENCES cargas (carga_id),
    CONSTRAINT entrega_despues_de_pedido CHECK (fecha_entrega >= fecha_pedido)
);

CREATE TABLE IF NOT EXISTS lineas_pedido (
    pedido_id        INT NOT NULL REFERENCES pedidos (pedido_id) ON DELETE CASCADE,
    producto_id      INT NOT NULL REFERENCES productos (producto_id),
    unidades         INT NOT NULL CHECK (unidades > 0),
    precio_unitario  NUMERIC(10, 2) NOT NULL CHECK (precio_unitario > 0),
    total            NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (pedido_id, producto_id),
    CONSTRAINT total_cuadra CHECK (total = unidades * precio_unitario)
);

-- Índices para las consultas del tablero: por día de entrega y por producto
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha_entrega ON pedidos (fecha_entrega);
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos (cliente_id);
CREATE INDEX IF NOT EXISTS idx_lineas_producto ON lineas_pedido (producto_id);
CREATE INDEX IF NOT EXISTS idx_cargas_recibida ON cargas (recibida_en DESC);

-- La misma forma que el CSV limpio, para que el tablero lea igual de S3 o de aquí
CREATE OR REPLACE VIEW v_lineas AS
SELECT p.pedido_id, p.cliente_id, p.fecha_pedido, to_char(p.hora_pedido, 'HH24:MI') AS hora_pedido,
       p.fecha_entrega, pr.nombre AS producto, pr.categoria, l.unidades,
       l.precio_unitario::float AS precio_unitario, l.total::float AS total,
       p.canal, p.entrega, p.metodo_pago
FROM lineas_pedido l
JOIN pedidos p   USING (pedido_id)
JOIN productos pr USING (producto_id);

CREATE OR REPLACE VIEW v_ventas_diarias AS
SELECT p.fecha_entrega AS fecha, count(DISTINCT p.pedido_id) AS pedidos,
       sum(l.unidades) AS unidades, sum(l.total)::float AS venta
FROM pedidos p JOIN lineas_pedido l USING (pedido_id)
GROUP BY p.fecha_entrega;
