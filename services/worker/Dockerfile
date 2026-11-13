# syntax=docker/dockerfile:1
# Worker que consume la cola en un ciclo (docker compose y la VM de E2).
#   docker build -f services/worker/Dockerfile -t salome-worker .
FROM python:3.13-slim AS dependencias
WORKDIR /w
COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir --prefix=/instalado -r requirements.txt

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=dependencias /instalado /usr/local
WORKDIR /app
COPY services/worker/limpieza.py services/worker/db.py services/worker/worker.py ./
COPY services/worker/referencia/ ./referencia/
USER app
CMD ["python", "worker.py"]
