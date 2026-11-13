#!/usr/bin/env bash
# E2 · Instala ingesta, worker y tablero en la instancia EC2 (Amazon Linux 2023) como servicios de systemd.
# Se corre dentro del servidor desde Session Manager (no hay SSH):
#
#   sudo CUENTA=... QUEUE_URL=... DB_HOST=... DB_PASSWORD=... \
#        PW_WORKER=... PW_INGESTA=... PW_TABLERO=... bash infra/ec2/instalar_servicios.sh
#
# Las contraseñas quedan en /etc/salome/*.env con permisos 600; nunca en el repositorio.
set -euo pipefail
: "${CUENTA:?}" "${QUEUE_URL:?}" "${DB_HOST:?}" "${DB_PASSWORD:?}" "${PW_WORKER:?}" "${PW_INGESTA:?}" "${PW_TABLERO:?}"
REGION=us-east-2
BUCKET=data-startup-salome-13454721
REPO=https://github.com/Vogelito09-lab/data-startup-postreria.git
DIR=/opt/salome

dnf install -y python3.13 python3.13-pip git postgresql16 >/dev/null
id salome >/dev/null 2>&1 || useradd --system --create-home --shell /sbin/nologin salome
if [ -d $DIR/.git ]; then git -C $DIR pull --ff-only; else git clone $REPO $DIR; fi
python3.13 -m venv $DIR/.venv
$DIR/.venv/bin/pip install -q -r $DIR/requirements.txt
chown -R salome:salome $DIR

# Un perfil de AWS por servicio. Cada uno asume su propio rol a partir del rol base del servidor.
mkdir -p /etc/salome
cat > /etc/salome/aws_config <<EOF
[default]
region = $REGION
EOF
for s in ingesta worker tablero; do cat >> /etc/salome/aws_config <<EOF

[profile $s]
role_arn = arn:aws:iam::$CUENTA:role/salome-$s
credential_source = Ec2InstanceMetadata
region = $REGION
EOF
done

# Esquema y usuarios de base de datos (con el usuario maestro, una sola vez)
ADMIN="postgresql://salome_admin:${DB_PASSWORD}@${DB_HOST}:5432/salome?sslmode=require"
psql "$ADMIN" -q -f $DIR/infra/sql/esquema.sql
psql "$ADMIN" -q -v pw_worker="'$PW_WORKER'" -v pw_ingesta="'$PW_INGESTA'" -v pw_tablero="'$PW_TABLERO'" \
  -f $DIR/infra/sql/usuarios.sql

comun="AWS_CONFIG_FILE=/etc/salome/aws_config
BUCKET=$BUCKET
QUEUE_URL=$QUEUE_URL"
printf '%s\nAWS_PROFILE=ingesta\nDATABASE_URL=postgresql://salome_ingesta:%s@%s:5432/salome?sslmode=require\n' "$comun" "$PW_INGESTA" "$DB_HOST" > /etc/salome/ingesta.env
printf '%s\nAWS_PROFILE=worker\nDATABASE_URL=postgresql://salome_worker:%s@%s:5432/salome?sslmode=require\n' "$comun" "$PW_WORKER" "$DB_HOST" > /etc/salome/worker.env
printf '%s\nAWS_PROFILE=tablero\nFUENTE=postgres\nDATABASE_URL=postgresql://salome_tablero:%s@%s:5432/salome?sslmode=require\n' "$comun" "$PW_TABLERO" "$DB_HOST" > /etc/salome/tablero.env
chown root:salome /etc/salome/*.env /etc/salome/aws_config
chmod 640 /etc/salome/*.env /etc/salome/aws_config

cp $DIR/infra/ec2/systemd/salome-*.service /etc/systemd/system/
systemctl disable --now streamlit-tablero.service 2>/dev/null || true   # el servicio de E1
systemctl daemon-reload
systemctl enable --now salome-ingesta salome-worker salome-tablero
sleep 5
systemctl --no-pager --lines=3 status salome-ingesta salome-worker salome-tablero
curl -s localhost:8000/salud && echo
