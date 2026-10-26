#!/bin/bash
# Instala y arranca el tablero de Salome en una instancia EC2 (Amazon Linux 2023).
# Se pega en "User data" al lanzar la instancia. No lleva llaves: el servidor
# lee S3 con el rol de IAM "tablero-salome-ec2" asignado a la instancia.
set -eux
BUCKET="data-startup-salome-25460344"

dnf install -y git python3.11 python3.11-pip

# 1 GB de swap para que la instalacion no se quede sin memoria en t3.micro
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo "/swapfile swap swap defaults 0 0" >> /etc/fstab

git clone https://github.com/Vogelito09-lab/data-startup-postreria.git /opt/app
cd /opt/app
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/tablero.service <<SERVICIO
[Unit]
Description=Tablero de Salome (Streamlit)
After=network-online.target

[Service]
WorkingDirectory=/opt/app
Environment=S3_BUCKET=${BUCKET}
Environment=AWS_DEFAULT_REGION=us-east-2
ExecStart=/opt/app/.venv/bin/python -m streamlit run services/tablero/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
SERVICIO

systemctl daemon-reload
systemctl enable --now tablero
