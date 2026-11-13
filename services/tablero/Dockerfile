# syntax=docker/dockerfile:1
# Construir desde la raíz del repositorio:  docker build -f services/tablero/Dockerfile -t salome-tablero .
FROM python:3.13-slim AS dependencias
WORKDIR /w
COPY services/tablero/requirements.txt .
RUN pip install --no-cache-dir --prefix=/instalado -r requirements.txt

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=dependencias /instalado /usr/local
WORKDIR /app
COPY services/tablero/*.py ./
COPY services/tablero/referencia/ ./referencia/
COPY services/tablero/.streamlit/ ./.streamlit/
ENV HOME=/tmp
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)" || exit 1
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"]
