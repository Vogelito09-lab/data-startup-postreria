#!/usr/bin/env bash
# Construye las cuatro imágenes y las sube a ECR con la etiqueta dada (las etiquetas son inmutables).
#   bash infra/aws/subir_imagenes.sh 3
set -euo pipefail
V=${1:?versión}
R=us-east-2
CUENTA=$(aws sts get-caller-identity --query Account --output text)
REG=$CUENTA.dkr.ecr.$R.amazonaws.com
aws ecr get-login-password --region $R | docker login --username AWS --password-stdin $REG
for s in ingesta modelos tablero; do
  docker build --platform linux/amd64 -f services/$s/Dockerfile -t $REG/salome-$s:$V .
  docker push $REG/salome-$s:$V
done
docker build --platform linux/amd64 --provenance=false -f services/worker/Dockerfile.lambda -t $REG/salome-worker-lambda:$V .
docker push $REG/salome-worker-lambda:$V
echo "Imágenes $V en $REG"
