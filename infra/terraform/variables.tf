variable "region" {
  type    = string
  default = "us-east-2"
}

variable "entorno" {
  description = "prod usa los nombres reales (se importan los recursos de E1 y E2). prueba crea copias con sufijo que se pueden destruir sin riesgo."
  type        = string
  default     = "prueba"
  validation {
    condition     = contains(["prod", "prueba"], var.entorno)
    error_message = "entorno debe ser prod o prueba."
  }
}

variable "bucket_base" {
  type    = string
  default = "data-startup-salome-13454721"
}

variable "crear_lambda" {
  description = "Crear la función del worker. Requiere haber subido la imagen a ECR (worker_imagen)."
  type        = bool
  default     = false
}

variable "worker_imagen" {
  description = "URI de la imagen del worker en ECR, por ejemplo <cuenta>.dkr.ecr.us-east-2.amazonaws.com/salome-worker-lambda:3"
  type        = string
  default     = ""
}

variable "database_url" {
  description = "Cadena de conexión del usuario salome_worker. Se pasa por TF_VAR_database_url, nunca en un archivo."
  type        = string
  default     = ""
  sensitive   = true
}

variable "rds_security_group_id" {
  description = "Grupo de seguridad de la RDS (salome-rds) para permitir 5432 desde la Lambda y desde ECS."
  type        = string
  default     = ""
}
