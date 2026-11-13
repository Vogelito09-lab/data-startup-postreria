# Mínimo privilegio, igual que en E2, ahora declarado. Cada política nombra exactamente los
# prefijos del bucket y la cola que su servicio usa.

locals {
  raw_arn   = "${aws_s3_bucket.lago.arn}/raw/pedidos/*"
  clean_arn = "${aws_s3_bucket.lago.arn}/clean/pedidos/*"

  politica_ingesta = {
    Version = "2012-10-17"
    Statement = [
      { Sid = "EscribeSoloEnRaw", Effect = "Allow", Action = "s3:PutObject", Resource = local.raw_arn },
      { Sid = "PublicaEnLaCola", Effect = "Allow", Action = "sqs:SendMessage", Resource = aws_sqs_queue.pedidos.arn },
    ]
  }
  politica_worker = {
    Version = "2012-10-17"
    Statement = [
      { Sid = "LeeRaw", Effect = "Allow", Action = "s3:GetObject", Resource = local.raw_arn },
      { Sid = "LeeYEscribeClean", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = local.clean_arn },
      { Sid = "ListarSoloEsosPrefijos", Effect = "Allow", Action = "s3:ListBucket", Resource = aws_s3_bucket.lago.arn,
      Condition = { StringLike = { "s3:prefix" = ["raw/pedidos/*", "clean/pedidos/*"] } } },
      { Sid = "ConsumeLaCola", Effect = "Allow",
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"],
      Resource = aws_sqs_queue.pedidos.arn },
    ]
  }
  politica_tablero = {
    Version   = "2012-10-17"
    Statement = [{ Sid = "TableroSoloLecturaClean", Effect = "Allow", Action = "s3:GetObject", Resource = local.clean_arn }]
  }
}

data "aws_iam_policy_document" "confia_en" {
  for_each = {
    ec2    = "ec2.amazonaws.com"
    lambda = "lambda.amazonaws.com"
    tareas = "ecs-tasks.amazonaws.com"
    ecs    = "ecs.amazonaws.com"
  }
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = [each.value]
    }
  }
}

# ---------------------------------------------------------------- EC2 de E2 (se mantiene mientras se migra)
resource "aws_iam_role" "ec2_base" {
  name               = "${local.nombre}-ec2-base"
  assume_role_policy = data.aws_iam_policy_document.confia_en["ec2"].json
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_base.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_base" {
  name = "${local.nombre}-ec2-base"
  role = aws_iam_role.ec2_base.name
}

resource "aws_iam_role" "servicio_vm" {
  for_each = { ingesta = local.politica_ingesta, worker = local.politica_worker, tablero = local.politica_tablero }
  name     = "${local.nombre}-${each.key}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = aws_iam_role.ec2_base.arn } }]
  })
}

resource "aws_iam_role_policy" "servicio_vm" {
  for_each = { ingesta = local.politica_ingesta, worker = local.politica_worker, tablero = local.politica_tablero }
  name     = "${local.nombre}-${each.key}-minimo"
  role     = aws_iam_role.servicio_vm[each.key].id
  policy   = jsonencode(each.value)
}

resource "aws_iam_role_policy" "ec2_asume" {
  name = "AsumirRolesDeServicio"
  role = aws_iam_role.ec2_base.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Resource = [for r in aws_iam_role.servicio_vm : r.arn] }]
  })
}

# ---------------------------------------------------------------- Lambda del worker
resource "aws_iam_role" "lambda_worker" {
  name               = "${local.nombre}-lambda-worker"
  assume_role_policy = data.aws_iam_policy_document.confia_en["lambda"].json
}

resource "aws_iam_role_policy" "lambda_worker" {
  name   = "worker-minimo"
  role   = aws_iam_role.lambda_worker.id
  policy = jsonencode(local.politica_worker)
}

# Crear interfaces de red en la VPC y escribir en CloudWatch Logs
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# ---------------------------------------------------------------- ECS Express Mode
resource "aws_iam_role" "ecs_ejecucion" {
  name               = "${local.nombre}-ecs-ejecucion"
  assume_role_policy = data.aws_iam_policy_document.confia_en["tareas"].json
}

resource "aws_iam_role_policy_attachment" "ecs_ejecucion" {
  role       = aws_iam_role.ecs_ejecucion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# La cadena de conexión de cada servicio vive en Parameter Store (SecureString, nivel estándar sin costo)
resource "aws_iam_role_policy" "ecs_parametros" {
  name = "LeerParametrosSalome"
  role = aws_iam_role.ecs_ejecucion.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect   = "Allow", Action = "ssm:GetParameters",
      Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.actual.account_id}:parameter/${local.nombre}/*" },
      { Effect = "Allow", Action = "kms:Decrypt", Resource = "*",
      Condition = { StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com" } } },
    ]
  })
}

resource "aws_iam_role" "ecs_infraestructura" {
  name               = "${local.nombre}-ecs-infraestructura"
  assume_role_policy = data.aws_iam_policy_document.confia_en["ecs"].json
}

resource "aws_iam_role_policy_attachment" "ecs_infraestructura" {
  role       = aws_iam_role.ecs_infraestructura.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}

# Rol que usa el código dentro de cada contenedor. Modelos y tablero leen PostgreSQL y no tocan AWS.
resource "aws_iam_role" "tarea" {
  for_each           = toset(["ingesta", "modelos", "tablero"])
  name               = "${local.nombre}-tarea-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.confia_en["tareas"].json
}

resource "aws_iam_role_policy" "tarea_ingesta" {
  name   = "ingesta-minimo"
  role   = aws_iam_role.tarea["ingesta"].id
  policy = jsonencode(local.politica_ingesta)
}
