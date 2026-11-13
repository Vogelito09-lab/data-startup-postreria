terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
  # Estado local para el proyecto. Con más personas se movería a un bucket con bloqueo.
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      proyecto   = "data-startup-salome"
      entorno    = var.entorno
      gestionado = "terraform"
    }
  }
}
