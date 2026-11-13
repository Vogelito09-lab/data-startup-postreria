# Recursos reales. Antes del primer apply, importar lo que se creó a mano en E1 y E2: ./importar_prod.sh
entorno      = "prod"
crear_lambda = true
# worker_imagen y rds_security_group_id se pasan al correr; database_url por TF_VAR_database_url
