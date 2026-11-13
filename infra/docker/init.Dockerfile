# Contenedor de un solo uso para docker compose: crea bucket y colas en moto y aplica el esquema.
FROM python:3.13-slim
RUN pip install --no-cache-dir boto3==1.44.1 psycopg2-binary==2.9.13 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY scripts/preparar_local.py ./scripts/
COPY infra/sql/ ./infra/sql/
CMD ["sh", "-c", "python scripts/preparar_local.py --db \"$ADMIN_URL\" && psql \"$ADMIN_URL\" -q -v pw_worker=\"'$PW_WORKER'\" -v pw_ingesta=\"'$PW_INGESTA'\" -v pw_tablero=\"'$PW_TABLERO'\" -f infra/sql/usuarios.sql && echo listo"]
