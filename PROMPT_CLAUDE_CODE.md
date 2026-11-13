# Instrucciones para Claude Code: evidencias de AWS del proyecto Salomé

Trabajas en el repositorio `data-startup-postreria` (proyecto DATA STARTUP, Cómputo en la Nube IAD-2408, TecNM Colima). Equipo: Jarom Cortes Pérez (Cloud Lead) y Carlos Antonio Vogel Romero (Data Lead). Los entregables E0, E1, E2 y E3 ya están escritos en `docs/*.md` y sus PDF se generan con `python scripts/docs_a_pdf.py`. Lo que falta es que lo que describen exista de verdad en AWS y tomar 19 capturas de evidencia.

Tu trabajo: crear y desplegar todo lo que describen los documentos, guiarme para tomar cada captura, poner las capturas en `docs/img/evidencia/` con el nombre exacto, actualizar las URL reales en los documentos y volver a generar los PDF.

## Reglas

1. Lee primero, completos: `README.md`, `docs/E0-propuesta.md`, `docs/E1-dashboard.md`, `docs/E2-cimientos.md`, `docs/E3-produccion.md` y `docs/img/evidencia/LEEME.md`. Lo que ahí se afirma es lo que tiene que quedar construido. Si algo no se puede hacer igual, detente y dime qué cambiar en el documento; no dejes una afirmación falsa.
2. Región `us-east-2` (Ohio) siempre. Nunca uses la cuenta raíz para operar: usa tu usuario de IAM con `aws login --profile salome` (no IAM Identity Center: obliga a crear una Organization y se pierde el Plan gratuito).
3. Contraseñas, códigos de MFA y aceptar términos los hago yo. Tú me dices exactamente dónde y qué.
4. Antes de crear algo que cobre (EC2, RDS, ECS, balanceadores) dime qué es y espera mi "sí". Al final apaga o borra lo que cobra.
5. Ninguna llave, contraseña ni `terraform.tfstate` entra al repositorio. Revisa `git status` antes de cada commit.
6. Las capturas son reales: tú ejecutas el comando o abres la página y yo tomo la captura. Nunca generes una imagen que imite una consola o una terminal.
7. Avanza por fases y dime al terminar cada una qué capturas quedaron y cuáles faltan.

## Fase 0. Preparación (sin costo)

1. Verifica que existan: AWS CLI v2, Docker, kind, kubectl, Terraform 1.6 o superior, Python 3.13, `gh`, pandoc y git. Lo que falte, dime cómo instalarlo en mi sistema operativo.
2. `python -m pip install -r requirements-dev.txt` y `python -m playwright install chromium` (los PDF se generan con Chromium).
3. `python -m pytest -q tests/` debe dar 43 pruebas que pasan y 1 que se omite (la de Lambda, que pide `TEST_DATABASE_URL`).
4. Bucket: los nombres de S3 son únicos en todo el mundo. Revisa si `data-startup-salome-13454721` está libre con `aws s3api head-bucket`. Si está ocupado por otra cuenta, elige `data-startup-salome-<8 dígitos>`, avísame y reemplázalo en todo el repositorio (`grep -rn 13454721`), incluidos los documentos y las políticas de `infra/iam/`.
5. GitHub: el repositorio es `https://github.com/Vogelito09-lab/data-startup-postreria`. Si no existe, créalo con `gh repo create`, sube el código y agrega a los dos integrantes como colaboradores. `data/historial/` está en `.gitignore` a propósito: no lo subas. Crea las etiquetas `e0`, `e1`, `e2` y `e3` cuando cada fase quede lista.

## Fase 1. E0: la cuenta (casi sin costo)

| Captura | Qué hacer | Dónde tomarla |
|---|---|---|
| `e0_plan_gratuito.png` | Nada que crear | Consola, Billing and Cost Management > Free Tier / plan de la cuenta |
| `e0_budgets.png` | Crear en AWS Budgets el presupuesto "zero spend" con aviso por correo | Lista de Budgets |
| `e0_raiz_mfa.png` | Con la raíz: MFA asignado y ninguna llave de acceso (lo hago yo, tú me guías) | IAM > Security credentials de la raíz |
| `e0_identity_center.png` | Un usuario de IAM por integrante, cada uno con MFA | IAM > Usuarios |
| `e0_github.png` | Colaboradores agregados | GitHub > Settings > Collaborators |

## Fase 2. E1: bucket y tablero en EC2 (cobra la EC2 si pasa la capa gratuita)

Construye exactamente lo de `docs/E1-dashboard.md`, sección 7:

1. Bucket con acceso público bloqueado y cifrado SSE-S3. Sube `data/historial/historial_hasta_2026-10-24.csv` a `raw/pedidos/fecha_carga=2026-10-24/historial.csv`, corre `python services/worker/limpieza.py data/historial/historial_hasta_2026-10-24.csv /tmp/clean.csv` y sube el resultado a `clean/pedidos/pedidos_salome_clean.csv`. Debe dar 2,606 renglones limpios.
2. Rol de la EC2 con la política `TableroSoloLecturaClean` (`infra/iam/politica-tablero.json`).
3. EC2 t3.micro llamada `tablero-salome`, Amazon Linux 2023, sin par de llaves, con Session Manager. Grupo de seguridad con solo el 8501 abierto (sin SSH).
4. En la instancia, por Session Manager: clona el repo, instala `requirements.txt` y deja el tablero (`services/tablero/app.py`) como servicio de systemd con `FUENTE=s3`.

Capturas: `e1_bucket.png` (bucket con `raw/` y `clean/` y el bloqueo de acceso público), `e1_tablero_ec2.png` (tablero en `http://<ip>:8501` con la fuente `s3://...` en la barra lateral), `e1_grupo_seguridad.png` (reglas de entrada) y `e1_rol_iam.png` (rol de la EC2 con su política).

Anota la IP pública: va en la tabla de arriba de `docs/E1-dashboard.md`, que hoy dice `18.191.145.103`.

## Fase 3. E2: ingesta, cola, worker y RDS (cobra la RDS si pasa la capa gratuita)

1. `export MI_IP=$(curl -s https://checkip.amazonaws.com)/32` y `DB_PASSWORD` (la escribo yo), luego `bash infra/aws/crear_infra_e2.sh`. Crea colas, roles por servicio, la RDS db.t4g.micro y la regla del 8000 solo para mi IP. Guarda lo que imprime.
2. En la EC2, por Session Manager: `infra/ec2/instalar_servicios.sh` con las variables del paso 1 (instrucciones al inicio del script). Quedan ingesta, worker y tablero (ahora `FUENTE=postgres`) en systemd.
3. `bash infra/aws/probar_privilegios.sh` → captura `e2_privilegios.png` (los 16 resultados esperados).
4. `e2_raiz_mfa.png`: la misma pantalla de MFA de la raíz que en E0.
5. Sube primero el historial y luego la semana nueva:
   `API=http://<ip>:8000 bash tests/demo_punta_a_punta.sh data/historial/historial_hasta_2026-10-24.csv`
   `API=http://<ip>:8000 bash tests/demo_punta_a_punta.sh`
   Captura `e2_demo_ec2.png` de la segunda (debe mostrar `procesada` y el tiempo).
6. `e2_tablero_cargas.png`: el tablero con última fecha 31/10/2026 y el panel de últimas cargas en la barra lateral.
7. Compara con `docs/E2-cimientos.md` sección 6: deben quedar 2,614 renglones, 1,963 pedidos y $789,297 en la base. Si algún tiempo medido difiere mucho del documento, dímelo.

En `docs/E2-cimientos.md` cambia `<IP de tablero-salome>` por la IP real.

## Fase 4. E3: contenedores, Kubernetes, Terraform, ECS y Lambda (es lo que más cobra)

1. `docker compose up --build` → `e3_compose.png`: `docker compose ps` con los siete servicios y el tablero en `localhost:8501` en el navegador. Luego `docker compose down`.
2. `bash k8s/levantar_kind.sh`. Con el clúster arriba corre Locust contra los modelos en kind (`locust -f tests/locustfile.py --host http://localhost:8100 --headless -u 50 -r 5 -t 3m`; kind expone el NodePort 30100 en el puerto 8100) y en otra terminal `kubectl -n salome get hpa modelos --watch` → `e3_hpa.png` mientras sube de réplicas. Para que escale, agrega la variable `CACHE_PRONOSTICO=0` al contenedor del Deployment de modelos (`kubectl -n salome set env deployment/modelos CACHE_PRONOSTICO=0`) durante la prueba. Al terminar, `kind delete cluster --name salome`.
3. Terraform, entorno de prueba: `init`, `workspace new prueba`, `apply -var-file=prueba.tfvars`, `destroy -var-file=prueba.tfvars` y otra vez `apply` → `e3_terraform.png` con el destroy y el apply con su número de recursos. Después `destroy` otra vez para no dejar la copia.
4. Producción: `workspace new prod`, `bash importar_prod.sh` y `apply -var-file=prod.tfvars` (pasa `worker_imagen` y `rds_security_group_id`; la cadena de conexión por `TF_VAR_database_url`).
5. `bash infra/aws/subir_imagenes.sh 3`, los parámetros de Parameter Store que indica el inicio de `infra/aws/desplegar_ecs.py`, y `python infra/aws/desplegar_ecs.py --version 3` → `e3_ecs.png`: consola de ECS con los tres servicios y sus URLs.
6. Lambda: sube la semana a la ingesta de ECS (`API=https://<ingesta> INGESTA_TOKEN=<la llave de /salome/ingesta/TOKEN> bash tests/demo_punta_a_punta.sh`) → `e3_lambda_logs.png`: CloudWatch Logs de la Lambda procesando la semana del 25 al 31 de octubre.
7. Prueba de carga en la nube: pon `CACHE_PRONOSTICO=0` en el servicio de modelos y corre `locust -f tests/locustfile.py --host https://<modelos> --headless -u 50 -r 5 -t 3m --csv docs/carga/ecs` → `e3_locust_ecs.png` con Locust y las tareas que levantó el autoescalado. Luego regresa `CACHE_PRONOSTICO=1`.

En `docs/E3-produccion.md` y `README.md` cambia los `<id>` de las URL de ECS por los reales.

## Fase 5. Cerrar

1. Revisa que las 19 capturas estén en `docs/img/evidencia/` con el nombre exacto de `docs/img/evidencia/LEEME.md`.
2. `python scripts/docs_a_pdf.py`. No debe imprimir "capturas pendientes" en ningún documento. Abre los cuatro PDF y revisa que cada imagen se lea y quede en su lugar.
3. `python -m pytest -q tests/` otra vez.
4. Apaga lo que cobra: servicios de ECS a cero tareas o borrados, `aws rds stop-db-instance --db-instance-identifier salome-db` y la EC2 detenida. Dime qué quedó encendido y cuánto cuesta por día.
5. Commit, push y etiqueta `e3`.
6. Rehaz las carpetas de entrega:
   - `Computo_en_la_Nube/`: los cuatro PDF de `docs/` y un zip del repositorio sin `__pycache__`, `.pytest_cache`, `.terraform` ni `terraform.tfstate*`.
   - `Analitica_de_Datos/`: no cambia, no la toques.
