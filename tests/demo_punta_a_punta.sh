#!/usr/bin/env bash
# Demostración en vivo de E2: sube la semana nueva por la API y mide cuánto tarda en quedar limpia.
#   API=http://<ip-de-la-ec2>:8000 bash tests/demo_punta_a_punta.sh [archivo.csv]
#   En ECS:  API=https://salome-ingesta....on.aws INGESTA_TOKEN=... bash tests/demo_punta_a_punta.sh
set -euo pipefail
API=${API:-http://localhost:8000}
ARCHIVO=${1:-data/sample/semana_2026-10-25.csv}
inicio=$(date +%s)
echo "Subiendo $ARCHIVO a $API ..."
LLAVE=(); [ -n "${INGESTA_TOKEN:-}" ] && LLAVE=(-H "X-Api-Key: $INGESTA_TOKEN")
R=$(curl -s -f "${LLAVE[@]}" -F "archivo=@$ARCHIVO" "$API/pedidos/csv")
echo "$R"
ID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin)['carga_id'])")
for i in $(seq 1 150); do
  E=$(curl -s "${LLAVE[@]}" "$API/cargas/$ID" | python3 -c "import sys,json;print(json.load(sys.stdin)['estado'])")
  [ "$E" = procesada ] || [ "$E" = error ] && break
  sleep 2
done
echo "Estado: $E después de $(( $(date +%s) - inicio )) segundos"
curl -s "${LLAVE[@]}" "$API/cargas/$ID" | python3 -m json.tool
echo "Abre el tablero y pulsa 'Actualizar ahora' (o espera 60 s): la última fecha debe ser la del archivo."
