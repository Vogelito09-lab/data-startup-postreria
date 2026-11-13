#!/usr/bin/env bash
# Trae a Terraform lo que E1 y E2 crearon con la consola y la CLI, para no duplicarlo ni borrarlo.
#   terraform workspace select prod || terraform workspace new prod
#   bash importar_prod.sh
set -euo pipefail
CUENTA=$(aws sts get-caller-identity --query Account --output text)
R=us-east-2
V="-var-file=prod.tfvars"
terraform import $V aws_s3_bucket.lago data-startup-salome-13454721
terraform import $V aws_s3_bucket_public_access_block.lago data-startup-salome-13454721
terraform import $V aws_s3_bucket_server_side_encryption_configuration.lago data-startup-salome-13454721
terraform import $V aws_sqs_queue.pedidos https://sqs.$R.amazonaws.com/$CUENTA/salome-pedidos
terraform import $V aws_sqs_queue.dlq https://sqs.$R.amazonaws.com/$CUENTA/salome-pedidos-dlq
terraform import $V aws_iam_role.ec2_base salome-ec2-base
terraform import $V aws_iam_instance_profile.ec2_base salome-ec2-base
for s in ingesta worker tablero; do
  terraform import $V "aws_iam_role.servicio_vm[\"$s\"]" salome-$s
  terraform import $V "aws_iam_role_policy.servicio_vm[\"$s\"]" salome-$s:salome-$s-minimo
done
terraform import $V aws_iam_role_policy.ec2_asume salome-ec2-base:AsumirRolesDeServicio
terraform import $V aws_iam_role_policy_attachment.ec2_ssm salome-ec2-base/arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
echo "Importado. Ahora: terraform plan $V  (los cambios que muestre son diferencias reales contra lo de E2)"
