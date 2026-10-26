# DulceDato Analytics · DATA STARTUP (Salomé)

Tablero con pronóstico para postrerías que venden por Instagram y WhatsApp: cuánto preparar de cada postre, a partir de sus propios pedidos. Primer cliente: Salomé.
Proyecto Integrador · Cómputo en la Nube × Analítica de Datos · TecNM Colima.

| Entrega | Documento |
|---|---|
| E0 · Propuesta | [`docs/E0-propuesta.md`](docs/E0-propuesta.md) |
| E1 · Dashboard empresarial | [`docs/E1-dashboard.md`](docs/E1-dashboard.md) · reporte de limpieza en [`docs/reporte-limpieza.md`](docs/reporte-limpieza.md) |

## Estructura

```
data-startup-postreria/
├── docs/                    # E0, E1, reporte de limpieza, capturas
├── data/sample/             # muestra pequeña (los datos completos no se suben)
├── scripts/
│   ├── generar_ventas.py    # pedidos de prueba para el pipeline
│   └── subir_s3.py          # carga raw/ y clean/ al bucket
├── services/
│   ├── worker/limpieza.py   # limpieza (en E2 la ejecuta el worker)
│   └── tablero/             # Streamlit: app.py + analisis.py
├── infra/
│   ├── iam/                 # políticas de solo lectura del tablero
│   └── ec2/user-data.sh     # instala y arranca el tablero en EC2
├── .streamlit/secrets.toml.example
└── requirements.txt
```

## Correr en tu computadora

```bash
pip install -r requirements.txt
python scripts/generar_ventas.py                 # crea data/raw/pedidos_salome.csv
python services/worker/limpieza.py               # crea data/clean/ y docs/reporte-limpieza.md
python scripts/subir_s3.py TU-BUCKET             # sube raw/ y clean/ a S3
streamlit run services/tablero/app.py            # lee de S3
```

Solo para desarrollar sin internet: `DATA_SOURCE=local streamlit run services/tablero/app.py`
(en Windows PowerShell: `$env:DATA_SOURCE="local"; streamlit run services/tablero/app.py`).

## Despliegue en AWS

Tablero publicado: http://18.191.145.103:8501

1. Cuenta con el **Plan gratuito**, región `us-east-2` (Ohio), alerta de **gasto cero** en Budgets y un acceso por integrante (Builder ID, página de Equipo).
2. Bucket S3 `data-startup-salome-25460344` (acceso público bloqueado, SSE-S3) con `raw/pedidos/fecha_carga=AAAA-MM-DD/` y `clean/pedidos/`.
3. Política `TableroSoloLecturaClean` ([`infra/iam/politica-tablero-ec2.json`](infra/iam/politica-tablero-ec2.json)) y rol `tablero-salome-ec2` (más `AmazonSSMManagedInstanceCore`).
4. Instancia EC2 `t3.micro` con Amazon Linux 2023, el rol anterior, solo el puerto 8501 abierto y [`infra/ec2/user-data.sh`](infra/ec2/user-data.sh) como datos de usuario.
5. Abrir `http://IP-PUBLICA:8501`. Detener la instancia cuando no se use.

## Subir a GitHub

```bash
git init && git add . && git commit -m "E0 y E1: propuesta, limpieza y tablero"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/data-startup-postreria.git
git push -u origin main
git tag e0 && git tag e1 && git push --tags
```

Agrega a tu compañero en *Settings → Collaborators*. Antes del push, revisa que `git status` **no** muestre `secrets.toml` ni la carpeta `data/raw`.
