# Data lake: raw/ (inmutable) y clean/. En prueba se puede destruir aunque tenga archivos.
resource "aws_s3_bucket" "lago" {
  bucket        = local.bucket
  force_destroy = var.entorno != "prod"
}

resource "aws_s3_bucket_public_access_block" "lago" {
  bucket                  = aws_s3_bucket.lago.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lago" {
  bucket = aws_s3_bucket.lago.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # en E4 cambia a aws:kms con llave propia
    }
  }
}

resource "aws_s3_bucket_versioning" "lago" {
  bucket = aws_s3_bucket.lago.id
  versioning_configuration {
    status = "Enabled" # un clean/ sobrescrito por error se puede recuperar
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lago" {
  bucket     = aws_s3_bucket.lago.id
  depends_on = [aws_s3_bucket_versioning.lago]
  rule {
    id     = "versiones-viejas-de-clean"
    status = "Enabled"
    filter {
      prefix = "clean/"
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# La Lambda vive en la VPC para llegar a RDS; este endpoint de S3 (tipo gateway, sin costo)
# le deja leer y escribir el bucket sin NAT. Solo se crea junto con la Lambda: una tabla de rutas
# no admite dos endpoints de S3, así que el entorno de prueba no lo duplica.
resource "aws_vpc_endpoint" "s3" {
  count             = var.crear_lambda ? 1 : 0
  vpc_id            = data.aws_vpc.default.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.default.ids
}
