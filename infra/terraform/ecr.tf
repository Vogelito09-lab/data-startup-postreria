resource "aws_ecr_repository" "imagenes" {
  for_each             = toset(["ingesta", "modelos", "tablero", "worker-lambda"])
  name                 = "${local.nombre}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.entorno != "prod"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "imagenes" {
  for_each   = aws_ecr_repository.imagenes
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las 5 imágenes más recientes"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}
