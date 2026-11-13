#!/usr/bin/env bash
# Levanta el sistema en Kubernetes local (kind) y deja el HPA listo para la prueba de carga.
# Requisitos: docker, kind, kubectl. Correr desde la raíz del repositorio.
set -euo pipefail
python services/worker/limpieza.py   # data/historial/pedidos_salome_clean.csv
docker build -f services/modelos/Dockerfile -t salome-modelos:3 .
docker build -f services/tablero/Dockerfile -t salome-tablero:3 .
kind create cluster --name salome --config k8s/kind-config.yaml
kind load docker-image salome-modelos:3 salome-tablero:3 --name salome
# metrics-server: sin él el HPA no ve el CPU. En kind necesita --kubelet-insecure-tls.
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl apply -f k8s/00-namespace.yaml -f k8s/01-config.yaml -f k8s/10-modelos.yaml -f k8s/20-tablero.yaml
kubectl -n salome rollout status deployment/modelos --timeout=180s
kubectl -n salome get deploy,svc,hpa,pods
echo "Tablero: http://localhost:8501 · modelos: http://localhost:8100/docs"
echo "Prueba de carga:  locust -f tests/locustfile.py --host http://localhost:8100 --headless -u 50 -r 5 -t 3m"
echo "En otra terminal:  kubectl -n salome get hpa modelos --watch"
