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
├── infra/iam/               # política de solo lectura del tablero
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

## Configurar AWS (una sola vez)

1. **Asegura la cuenta raíz.** Inicia sesión como raíz → menú de tu nombre → *Security credentials* → activa **MFA**. Captura.
2. **Alerta de presupuesto.** *Billing and Cost Management* → *Budgets* → *Create budget* → plantilla **Zero spend budget** → tu correo. Captura.
3. **Tu usuario IAM.** *IAM* → *Users* → *Create user* (`carlos-admin`) → acceso a la consola → política `AdministratorAccess` → actívale MFA. A partir de aquí **no vuelvas a usar la raíz**. Captura de la lista de usuarios.
4. **Bucket.** *S3* → *Create bucket* → nombre único, por ejemplo `data-startup-salome-carlos`, región `us-east-1`, *Block all public access* activado y cifrado por defecto (SSE-S3).
5. **Usuario del tablero (mínimo privilegio).** *IAM* → *Policies* → *Create policy* → pestaña JSON → pega `infra/iam/politica-tablero-solo-lectura.json` con el nombre de tu bucket → nómbrala `TableroSoloLecturaClean`. Luego crea el usuario `tablero-lector` **sin consola**, asígnale solo esa política y crea una *access key* (tipo "Application running outside AWS").
6. **Credenciales en tu computadora (fuera del código).** Instala la AWS CLI y corre `aws configure` con las llaves de tu usuario `carlos-admin` para subir datos. Para el tablero, copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`, pon el nombre del bucket y, si quieres, las llaves de `tablero-lector`.
7. **Sube los datos** con `python scripts/subir_s3.py TU-BUCKET` y abre el tablero. En la barra lateral debe decir `Fuente: s3://…`. Captura del bucket (carpetas `raw/` y `clean/`) y del tablero.

## Subir a GitHub

```bash
git init && git add . && git commit -m "E0 y E1: propuesta, limpieza y tablero"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/data-startup-postreria.git
git push -u origin main
git tag e0 && git tag e1 && git push --tags
```

Agrega a tu compañero en *Settings → Collaborators*. Antes del push, revisa que `git status` **no** muestre `secrets.toml` ni la carpeta `data/raw`.
