locals {
  sufijo = var.entorno == "prod" ? "" : "-${var.entorno}"
  bucket = "${var.bucket_base}${local.sufijo}"
  cola   = "salome-pedidos${local.sufijo}"
  nombre = "salome${local.sufijo}"
}

data "aws_caller_identity" "actual" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_route_tables" "default" {
  vpc_id = data.aws_vpc.default.id
}
