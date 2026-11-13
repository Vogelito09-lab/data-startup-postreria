resource "aws_security_group" "lambda" {
  name        = "${local.nombre}-lambda-worker"
  description = "Worker serverless: sin entrada; salida a RDS y al endpoint de S3"
  vpc_id      = data.aws_vpc.default.id
  egress {
    description = "Salida (RDS en 5432 y S3 por el endpoint)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_tareas" {
  name        = "${local.nombre}-ecs-tareas"
  description = "Tareas de ECS Express; el balanceador lo crea ECS"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "rds_desde" {
  for_each                 = var.rds_security_group_id == "" ? tomap({}) : tomap({ lambda = aws_security_group.lambda.id, ecs = aws_security_group.ecs_tareas.id })
  type                     = "ingress"
  description              = "PostgreSQL desde ${each.key}"
  security_group_id        = var.rds_security_group_id
  source_security_group_id = each.value
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.nombre}-worker"
  retention_in_days = 14
}

resource "aws_lambda_function" "worker" {
  count         = var.crear_lambda ? 1 : 0
  function_name = "${local.nombre}-worker"
  role          = aws_iam_role.lambda_worker.arn
  package_type  = "Image"
  image_uri     = var.worker_imagen
  architectures = ["x86_64"]
  timeout       = 60
  memory_size   = 1024 # pandas necesita memoria; más memoria también da más CPU
  environment {
    variables = {
      BUCKET       = aws_s3_bucket.lago.id
      DATABASE_URL = var.database_url
      LOG_LEVEL    = "INFO"
    }
  }
  vpc_config {
    subnet_ids         = data.aws_subnets.default.ids
    security_group_ids = [aws_security_group.lambda.id]
  }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy_attachment.lambda_vpc]
}

resource "aws_lambda_event_source_mapping" "cola" {
  count                              = var.crear_lambda ? 1 : 0
  event_source_arn                   = aws_sqs_queue.pedidos.arn
  function_name                      = aws_lambda_function.worker[0].arn
  batch_size                         = 5
  maximum_batching_window_in_seconds = 5
  function_response_types            = ["ReportBatchItemFailures"]
  scaling_config {
    maximum_concurrency = 2
  }
}
