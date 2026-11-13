# syntax=docker/dockerfile:1
# Construir desde la raíz del repositorio:  docker build -f services/ingesta/Dockerfile -t salome-ingesta .
FROM python:3.13-slim AS dependencias
WORKDIR /w
COPY services/ingesta/requirements.txt .
RUN pip install --no-cache-dir --prefix=/instalado -r requirements.txt

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=dependencias /instalado /usr/local
WORKDIR /app
COPY services/ingesta/app.py .
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/salud', timeout=4)" || exit 1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
