output "bucket" { value = aws_s3_bucket.lago.id }
output "queue_url" { value = aws_sqs_queue.pedidos.id }
output "dlq_url" { value = aws_sqs_queue.dlq.id }
output "ecr" { value = { for k, r in aws_ecr_repository.imagenes : k => r.repository_url } }
output "rol_ecs_ejecucion" { value = aws_iam_role.ecs_ejecucion.arn }
output "rol_ecs_infraestructura" { value = aws_iam_role.ecs_infraestructura.arn }
output "roles_tarea" { value = { for k, r in aws_iam_role.tarea : k => r.arn } }
output "sg_ecs_tareas" { value = aws_security_group.ecs_tareas.id }
output "subredes" { value = data.aws_subnets.default.ids }
output "lambda" { value = var.crear_lambda ? aws_lambda_function.worker[0].function_name : "sin crear (crear_lambda = false)" }
