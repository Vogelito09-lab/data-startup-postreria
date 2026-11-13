#!/usr/bin/env bash
# E2 · Demuestra que cada servicio solo puede hacer lo suyo. Se corre en el servidor (Session Manager):
#   sudo -u salome AWS_CONFIG_FILE=/etc/salome/aws_config QUEUE_URL=... bash infra/aws/probar_privilegios.sh
# Cada línea dice si el resultado fue el esperado. "PERMITIDO" o "DENEGADO" es lo que respondió AWS.
B=s3://data-startup-salome-13454721
: "${QUEUE_URL:?}"
echo prueba > /tmp/prueba.csv
ok=0; mal=0
probar() {  # perfil, esperado (si|no), descripción, comando...
  local perfil=$1 esperado=$2 desc=$3; shift 3
  if AWS_PROFILE=$perfil "$@" >/dev/null 2>&1; then r=si; else r=no; fi
  if [ "$r" = "$esperado" ]; then ok=$((ok+1)); m="OK "; else mal=$((mal+1)); m="MAL"; fi
  printf '%s  %-8s %-58s %s\n' "$m" "$perfil" "$desc" "$([ $r = si ] && echo PERMITIDO || echo DENEGADO)"
}
probar ingesta si "escribir en raw/"                     aws s3 cp /tmp/prueba.csv $B/raw/pedidos/_prueba_permisos.csv
probar ingesta si "publicar en la cola"                  aws sqs send-message --queue-url "$QUEUE_URL" --message-body '{"prueba":true}' --delay-seconds 900
probar ingesta no "leer clean/"                          aws s3 cp $B/clean/pedidos/pedidos_salome_clean.csv -
probar ingesta no "leer la cola"                         aws sqs receive-message --queue-url "$QUEUE_URL"
probar worker  si "leer raw/"                            aws s3 cp $B/raw/pedidos/_prueba_permisos.csv -
probar worker  si "escribir en clean/"                   aws s3 cp /tmp/prueba.csv $B/clean/pedidos/_prueba_permisos.csv
probar worker  no "escribir en raw/ (raw es inmutable)"  aws s3 cp /tmp/prueba.csv $B/raw/pedidos/otro.csv
probar worker  no "borrar en raw/"                       aws s3 rm $B/raw/pedidos/_prueba_permisos.csv
probar worker  no "borrar en clean/"                     aws s3 rm $B/clean/pedidos/pedidos_salome_clean.csv
probar worker  no "publicar en la cola"                  aws sqs send-message --queue-url "$QUEUE_URL" --message-body x
probar worker  no "listar todo el bucket"                aws s3 ls $B/
probar worker  no "ver usuarios de IAM"                  aws iam list-users
probar worker  no "crear un bucket"                      aws s3 mb s3://salome-prueba-$RANDOM
probar tablero si "leer clean/"                          aws s3 cp $B/clean/pedidos/pedidos_salome_clean.csv -
probar tablero no "escribir en clean/"                   aws s3 cp /tmp/prueba.csv $B/clean/pedidos/x.csv
probar tablero no "leer raw/"                            aws s3 cp $B/raw/pedidos/_prueba_permisos.csv -
echo "----"; echo "$ok resultados esperados, $mal inesperados"
echo "Nota: los dos archivos _prueba_permisos.csv se borran a mano desde la consola con un usuario del equipo."
