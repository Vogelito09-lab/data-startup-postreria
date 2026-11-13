-- Un usuario de base de datos por servicio, cada uno con lo mínimo que necesita.
-- Las contraseñas NO van aquí: se pasan al correr el script y se guardan en
-- /etc/salome/*.env en el servidor (fuera del repositorio). En E4 pasan a Secrets Manager.
--
--   psql "$DATABASE_URL_ADMIN" -v pw_worker="'...'" -v pw_ingesta="'...'" -v pw_tablero="'...'" -f infra/sql/usuarios.sql

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'salome_worker')  THEN CREATE ROLE salome_worker  LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'salome_ingesta') THEN CREATE ROLE salome_ingesta LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'salome_tablero') THEN CREATE ROLE salome_tablero LOGIN; END IF;
END $$;

ALTER ROLE salome_worker  PASSWORD :pw_worker;
ALTER ROLE salome_ingesta PASSWORD :pw_ingesta;
ALTER ROLE salome_tablero PASSWORD :pw_tablero;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO salome_worker, salome_ingesta, salome_tablero;

-- Ingesta: solo registra la carga y consulta su estado
GRANT SELECT, INSERT, UPDATE ON cargas TO salome_ingesta;

-- Worker: escribe pedidos y actualiza el estado de la carga; no puede borrar cargas ni tocar esquemas
GRANT SELECT, INSERT, UPDATE ON productos, clientes, pedidos TO salome_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON lineas_pedido TO salome_worker;
GRANT SELECT, INSERT, UPDATE ON cargas TO salome_worker;
GRANT USAGE ON SEQUENCE productos_producto_id_seq TO salome_worker;

-- Tablero: solo lee
GRANT SELECT ON v_lineas, v_ventas_diarias, cargas TO salome_tablero;
