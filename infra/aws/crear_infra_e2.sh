#!/usr/bin/env bash
# E2 · Crea con AWS CLI lo que E2 agrega sobre E1: colas, roles por servicio, base de datos y reglas de red.
# En E3 todo esto pasa a Terraform (infra/terraform). Se corre una sola vez desde CloudShell o desde una
# terminal con un usuario de IAM del equipo (nunca con la cuenta raíz).
#
#   export MI_IP=$(curl -s https://checkip.amazonaws.com)/32
#   export DB_PASSWORD='...'      # contraseña del usuario maestro de RDS; no se guarda en el repo
#   bash infra/aws/crear_infra_e2.sh
set -euo pipefail

REGION=us-east-2
BUCKET=data-startup-salome-13454721
INSTANCIA_NOMBRE=tablero-salome
CUENTA=$(aws sts get-caller-identity --query Account --output text)
AQUI=$(cd "$(dirname "$0")/.." && pwd)
export AWS_DEFAULT_REGION=$REGION
: "${MI_IP:?Define MI_IP con tu IP pública /32}"
: "${DB_PASSWORD:?Define DB_PASSWORD}"

echo "== 1. Colas SQS: principal + cola de mensajes fallidos (DLQ)"
DLQ_URL=$(aws sqs create-queue --queue-name salome-pedidos-dlq \
  --attributes MessageRetentionPeriod=1209600 --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
cat > /tmp/atributos-cola.json <<EOF
{
  "VisibilityTimeout": "120",
  "ReceiveMessageWaitTimeSeconds": "20",
  "MessageRetentionPeriod": "345600",
  "SqsManagedSseEnabled": "true",
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"$DLQ_ARN\",\"maxReceiveCount\":\"3\"}"
}
EOF
QUEUE_URL=$(aws sqs create-queue --queue-name salome-pedidos --attributes file:///tmp/atributos-cola.json --query QueueUrl --output text)
echo "   QUEUE_URL=$QUEUE_URL"

echo "== 2. Roles de IAM: uno base para el servidor y uno por servicio"
sub() { sed "s/CUENTA/$CUENTA/g" "$AQUI/iam/$1"; }
aws iam create-role --role-name salome-ec2-base --assume-role-policy-document file://"$AQUI/iam/confianza-ec2.json" >/dev/null
aws iam put-role-policy --role-name salome-ec2-base --policy-name AsumirRolesDeServicio --policy-document "$(sub politica-ec2-base.json)"
aws iam attach-role-policy --role-name salome-ec2-base --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam create-instance-profile --instance-profile-name salome-ec2-base >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name salome-ec2-base --role-name salome-ec2-base
sleep 10  # IAM tarda unos segundos en propagar el rol base antes de usarlo en otras confianzas
for s in ingesta worker tablero; do
  aws iam create-role --role-name salome-$s --assume-role-policy-document "$(sub confianza-servicio.json)" >/dev/null
  aws iam put-role-policy --role-name salome-$s --policy-name salome-$s-minimo --policy-document "$(sub politica-$s.json)"
  echo "   rol salome-$s listo"
done

echo "== 3. Servidor: cambiar el perfil de instancia de E1 por el nuevo"
INSTANCIA=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=$INSTANCIA_NOMBRE" "Name=instance-state-name,Values=running,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
ASOC=$(aws ec2 describe-iam-instance-profile-associations --filters Name=instance-id,Values="$INSTANCIA" \
  --query 'IamInstanceProfileAssociations[0].AssociationId' --output text)
if [ "$ASOC" != "None" ]; then
  aws ec2 replace-iam-instance-profile-association --association-id "$ASOC" --iam-instance-profile Name=salome-ec2-base >/dev/null
else
  aws ec2 associate-iam-instance-profile --instance-id "$INSTANCIA" --iam-instance-profile Name=salome-ec2-base >/dev/null
fi
SG_EC2=$(aws ec2 describe-instances --instance-ids "$INSTANCIA" --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
VPC=$(aws ec2 describe-instances --instance-ids "$INSTANCIA" --query 'Reservations[0].Instances[0].VpcId' --output text)
# La API de ingesta (8000) solo se abre a la IP del equipo. El tablero sigue en 8501 como en E1.
aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --ip-permissions \
  "IpProtocol=tcp,FromPort=8000,ToPort=8000,IpRanges=[{CidrIp=$MI_IP,Description=ingesta-solo-equipo}]" >/dev/null || true

echo "== 4. Base de datos RDS PostgreSQL privada"
SG_RDS=$(aws ec2 create-security-group --group-name salome-rds --description "PostgreSQL solo desde el servidor" \
  --vpc-id "$VPC" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --ip-permissions \
  "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_EC2,Description=desde-ec2}]" >/dev/null
aws rds create-db-instance \
  --db-instance-identifier salome-db --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro --allocated-storage 20 --storage-type gp2 \
  --master-username salome_admin --master-user-password "$DB_PASSWORD" --db-name salome \
  --vpc-security-group-ids "$SG_RDS" --no-publicly-accessible --no-multi-az \
  --storage-encrypted --backup-retention-period 1 --no-deletion-protection \
  --tags Key=proyecto,Value=data-startup-salome >/dev/null
echo "   esperando a que la base esté disponible (5 a 10 minutos)..."
aws rds wait db-instance-available --db-instance-identifier salome-db
DB_HOST=$(aws rds describe-db-instances --db-instance-identifier salome-db --query 'DBInstances[0].Endpoint.Address' --output text)

cat <<EOF

Listo. Anota estos valores para infra/ec2/instalar_servicios.sh (no los subas al repo):
  CUENTA=$CUENTA
  QUEUE_URL=$QUEUE_URL
  DLQ_URL=$DLQ_URL
  DB_HOST=$DB_HOST
  INSTANCIA=$INSTANCIA
EOF
