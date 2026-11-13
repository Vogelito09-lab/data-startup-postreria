# DulceDato Analytics · Salomé

Tablero y pronóstico de producción para Salomé, postrería casera que vende por WhatsApp, Instagram y Facebook en Villa de Álvarez, Colima. Proyecto integrador DATA STARTUP (Cómputo en la Nube IAD-2408 × Analítica de Datos IAD-2403, TecNM Campus Colima).

Equipo: Jarom Cortes Pérez (Cloud Lead) · Carlos Antonio Vogel Romero (Data Lead)

| Qué | Dónde |
|---|---|
| Tablero | `https://salome-tablero.<id>.ecs.us-east-2.on.aws` (ECS Express Mode) |
| API de modelos | `https://salome-modelos.<id>.ecs.us-east-2.on.aws/docs` |
| API de ingesta | `https://salome-ingesta.<id>.ecs.us-east-2.on.aws/docs` (pide `X-Api-Key`) |
| Entregables | `docs/E0-propuesta.md`, `docs/E1-dashboard.md`, `docs/E2-cimientos.md`, `docs/E3-produccion.md` |

## Cómo está armado

```
CSV / JSON ─► ingesta (ECS) ─► S3 raw/ ─► SQS ─► Lambda worker (limpieza.py) ─► S3 clean/ + PostgreSQL (RDS)
                                          └─► DLQ tras 3 intentos                          │
                                     tablero v3 (ECS) ◄── API de modelos (ECS: SARIMA + árbol) ◄┘
```

```
docs/              entregables, figuras, diagrama y resultados.json
data/historial/    historial de pedidos 2020 a 2026, catálogo y cierres (fuera de GitHub; viene en el zip y en S3)
data/sample/       muestra pequeña (200 renglones) y la semana de la demo
notebooks/         E1 limpieza y hallazgos · E2 series y regresión · E3 SARIMA y clasificador (ejecutados)
analitica/         Analítica de Datos: avances 1 y 2, notebook final y reporte ejecutivo
scripts/           figuras, notebooks, entrenamiento y entorno local
services/ingesta/  API FastAPI
services/worker/   limpieza.py, worker.py, db.py y tablas de referencia
services/tablero/  app.py (Streamlit), analitica.py, modelos_e2.py, fuente.py
services/modelos/  API /pronostico y /clasificar, nucleo.py
models/            modelos versionados (v1) y registro.json
k8s/               manifiestos (Deployment, Service, HPA) y kind
infra/terraform/   bucket, colas, roles, ECR y Lambda
infra/docker/      contenedor init de docker compose
infra/iam/         políticas de mínimo privilegio
infra/aws/         creación de colas, roles, RDS y prueba de privilegios
infra/ec2/         instalación en la EC2 y unidades de systemd
infra/sql/         esquema y usuarios de PostgreSQL
tests/             pruebas (pytest) y demo de punta a punta
```

## Correrlo en tu máquina

```bash
pip install -r requirements-dev.txt
python scripts/partir_demo.py                     # historial + semana nueva para la demo
python services/worker/limpieza.py                # CSV limpio y reporte de limpieza
python scripts/entrenar_e3.py                     # SARIMA + clasificador -> models/ (un minuto)
python -m pytest -q tests/                        # 44 pruebas (la de Lambda pide TEST_DATABASE_URL)
FUENTE=local RUTA_LOCAL=data/historial/pedidos_salome_clean.csv streamlit run services/tablero/app.py
```

Tubería completa sin nube (S3 y SQS emulados con moto, PostgreSQL local):

```bash
moto_server -p 5055 &
export AWS_ENDPOINT_URL=http://localhost:5055 AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=x AWS_DEFAULT_REGION=us-east-2
export BUCKET=data-startup-salome-13454721
python scripts/preparar_local.py --db postgresql://postgres@localhost:5432/salome   # imprime QUEUE_URL
export QUEUE_URL=...
(cd services/ingesta && DATABASE_URL=postgresql://postgres@localhost:5432/salome uvicorn app:app --port 8000 &)
(cd services/worker  && DATABASE_URL=postgresql://postgres@localhost:5432/salome python worker.py &)
bash tests/demo_punta_a_punta.sh data/historial/historial_hasta_2026-10-24.csv
bash tests/demo_punta_a_punta.sh
```

## Todo en contenedores (E3)

```bash
docker compose up --build          # PostgreSQL, moto, ingesta, worker, modelos y tablero
bash k8s/levantar_kind.sh          # Kubernetes local con HPA
```

## Desplegar en AWS (E3)

1. `terraform -chdir=infra/terraform apply -var-file=prod.tfvars` (después de `importar_prod.sh`).
2. `bash infra/aws/subir_imagenes.sh 3` y guardar `/salome/<servicio>/DATABASE_URL` y `/salome/ingesta/TOKEN` en Parameter Store (instrucciones al inicio de `desplegar_ecs.py`).
3. `python infra/aws/desplegar_ecs.py --version 3`.
4. Prueba de carga: `locust -f tests/locustfile.py --host https://<modelos> --headless -u 50 -r 5 -t 3m`.
5. Entre revisiones: bajar a cero las tareas de ECS o borrar los servicios, y detener la RDS.

## Desplegar en AWS (E2, en la EC2)

1. `infra/aws/crear_infra_e2.sh` con un usuario del equipo (no la raíz): colas, roles, RDS y regla del puerto 8000.
2. Por Session Manager en la EC2: `infra/ec2/instalar_servicios.sh` con las variables que imprimió el paso 1.
3. Subir el historial: `API=http://<ip>:8000 bash tests/demo_punta_a_punta.sh data/historial/historial_hasta_2026-10-24.csv`.
4. Probar permisos: `infra/aws/probar_privilegios.sh`.
5. Cuando no se use: detener la EC2 y `aws rds stop-db-instance --db-instance-identifier salome-db`.

## Datos

Historial de pedidos de Salomé del 5 de febrero de 2020 al 31 de octubre de 2026 (`data/historial/`): cerca de 2,000 pedidos de un negocio de una persona, con descanso los lunes, tope de cuatro pasteles enteros en un día normal, alzas de precio cada enero, temporadas mexicanas y los errores típicos de copiar pedidos de los chats a mano, que la limpieza corrige. No contiene nombres, teléfonos ni direcciones: cada cliente es un código.
