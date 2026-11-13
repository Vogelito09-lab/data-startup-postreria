# Bitácoras de los servicios de ECS Express (desplegados con infra/aws/desplegar_ecs.py).
# Se crean aquí para controlar cuánto tiempo se guardan y para que el destroy las limpie.
resource "aws_cloudwatch_log_group" "ecs" {
  for_each          = toset(["ingesta", "modelos", "tablero"])
  name              = "/ecs/${local.nombre}-${each.key}"
  retention_in_days = 14
}
