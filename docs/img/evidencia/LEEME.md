# Capturas de evidencia

Cada captura tomada en la consola de AWS o en la terminal se guarda aquí con el nombre exacto que usan
los documentos. Mientras falta, el PDF muestra un recuadro "Captura pendiente"; al agregarla y correr
`python scripts/docs_a_pdf.py`, aparece la imagen.

| Archivo | Documento | Qué debe mostrar |
|---|---|---|
| e0_plan_gratuito.png | E0 | Cuenta de AWS en el Plan gratuito (Billing) |
| e0_budgets.png | E0 | Alerta de gasto cero en AWS Budgets |
| e0_raiz_mfa.png | E0 | Cuenta raíz con MFA y sin llaves de acceso |
| e0_identity_center.png | E0 | Usuarios de IAM, uno por integrante |
| e0_github.png | E0 | Colaboradores del repositorio en GitHub |
| e1_bucket.png | E1 | Bucket con raw/ y clean/ y acceso público bloqueado |
| e1_tablero_ec2.png | E1 | Tablero en la EC2 con la fuente s3:// en la barra lateral |
| e1_grupo_seguridad.png | E1 | Grupo de seguridad con solo el 8501 |
| e1_rol_iam.png | E1 | Rol de la EC2 con TableroSoloLecturaClean |
| e2_privilegios.png | E2 | Salida de infra/aws/probar_privilegios.sh |
| e2_raiz_mfa.png | E2 | Cuenta raíz con MFA y sin llaves |
| e2_demo_ec2.png | E2 | tests/demo_punta_a_punta.sh contra la EC2 con el tiempo |
| e2_tablero_cargas.png | E2 | Tablero con fecha 31/10/2026 y panel de últimas cargas |
| e3_compose.png | E3 | docker compose ps y el tablero en localhost:8501 |
| e3_ecs.png | E3 | Consola de ECS con los tres servicios y sus URLs |
| e3_hpa.png | E3 | kubectl get hpa durante la prueba de carga |
| e3_lambda_logs.png | E3 | CloudWatch Logs de la Lambda |
| e3_locust_ecs.png | E3 | Locust contra ECS y tareas levantadas |
| e3_terraform.png | E3 | terraform destroy y apply |
