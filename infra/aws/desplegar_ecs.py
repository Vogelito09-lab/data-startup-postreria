"""E3 · Despliega ingesta, modelos y tablero en Amazon ECS Express Mode (Fargate + balanceador + autoescalado).

App Runner ya no acepta clientes nuevos; AWS recomienda Express Mode, que en una sola llamada crea el
servicio de Fargate, un balanceador con HTTPS en <servicio>.ecs.<región>.on.aws y el autoescalado.

Antes:
  1. terraform apply en infra/terraform (roles, ECR, grupo de seguridad de las tareas)
  2. subir las imágenes:  bash infra/aws/subir_imagenes.sh 3
  3. guardar cadenas de conexión en Parameter Store (una vez):
       aws ssm put-parameter --type SecureString --name /salome/ingesta/DATABASE_URL --value 'postgresql://...'
       (igual para /salome/modelos/DATABASE_URL y /salome/tablero/DATABASE_URL con salome_tablero)
       aws ssm put-parameter --type SecureString --name /salome/ingesta/TOKEN --value "$(openssl rand -hex 24)"
     La ingesta queda con URL pública, así que desde E3 exige el encabezado X-Api-Key.

Uso:
  python infra/aws/desplegar_ecs.py --version 3            # crea o actualiza los tres servicios
  python infra/aws/desplegar_ecs.py --version 3 --validar  # solo revisa los parámetros, sin llamar a AWS
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.validate import ParamValidator

REGION = "us-east-2"
TF = Path(__file__).resolve().parents[1] / "terraform"

SERVICIOS = {
    # nombre: puerto, salud, cpu, memoria, min, max, variables, ¿usa SQS/S3?
    "ingesta": dict(puerto=8000, salud="/salud", cpu="256", memoria="512", minimo=1, maximo=2, env={}),
    "modelos": dict(puerto=8100, salud="/salud", cpu="512", memoria="1024", minimo=1, maximo=4, env={"FUENTE": "postgres"}),
    "tablero": dict(puerto=8501, salud="/_stcore/health", cpu="512", memoria="1024", minimo=1, maximo=2,
                    env={"FUENTE": "postgres", "HOME": "/tmp"}),
}


def salidas_terraform() -> dict:
    out = subprocess.run(["terraform", f"-chdir={TF}", "output", "-json"], capture_output=True, text=True, check=True)
    return {k: v["value"] for k, v in json.loads(out.stdout).items()}


def parametros(nombre: str, cfg: dict, tf: dict, version: str, cuenta: str, modelos_url: str | None) -> dict:
    env = dict(cfg["env"])
    if nombre == "ingesta":
        env |= {"BUCKET": tf["bucket"], "QUEUE_URL": tf["queue_url"], "AWS_DEFAULT_REGION": REGION}
    if nombre == "tablero" and modelos_url:
        env["MODELOS_URL"] = modelos_url
    return {
        "serviceName": f"salome-{nombre}",
        "executionRoleArn": tf["rol_ecs_ejecucion"],
        "infrastructureRoleArn": tf["rol_ecs_infraestructura"],
        "taskRoleArn": tf["roles_tarea"][nombre],
        "healthCheckPath": cfg["salud"],
        "cpu": cfg["cpu"],
        "memory": cfg["memoria"],
        "cpuArchitecture": "X86_64",
        "networkConfiguration": {"subnets": tf["subredes"], "securityGroups": [tf["sg_ecs_tareas"]]},
        "primaryContainer": {
            "image": f"{tf['ecr'][nombre]}:{version}",
            "containerPort": cfg["puerto"],
            "environment": [{"name": k, "value": v} for k, v in env.items()],
            "secrets": [{"name": "DATABASE_URL",
                         "valueFrom": f"arn:aws:ssm:{REGION}:{cuenta}:parameter/salome/{nombre}/DATABASE_URL"}]
                       + ([{"name": "INGESTA_TOKEN", "valueFrom": f"arn:aws:ssm:{REGION}:{cuenta}:parameter/salome/ingesta/TOKEN"}]
                          if nombre == "ingesta" else []),
            "awsLogsConfiguration": {"logGroup": f"/ecs/salome-{nombre}", "logStreamPrefix": nombre},
        },
        "scalingTarget": {"minTaskCount": cfg["minimo"], "maxTaskCount": cfg["maximo"],
                          "autoScalingMetric": "AVERAGE_CPU", "autoScalingTargetValue": 60},
        "tags": [{"key": "proyecto", "value": "data-startup-salome"}],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="etiqueta de las imágenes en ECR")
    ap.add_argument("--validar", action="store_true")
    a = ap.parse_args()
    ecs = boto3.client("ecs", region_name=REGION)
    modelo = ecs.meta.service_model.operation_model("CreateExpressGatewayService").input_shape
    if a.validar:
        tf = {"bucket": "b", "queue_url": "q", "rol_ecs_ejecucion": "arn:aws:iam::123456789012:role/x",
              "rol_ecs_infraestructura": "arn:aws:iam::123456789012:role/y", "subredes": ["subnet-1"], "sg_ecs_tareas": "sg-1",
              "roles_tarea": {k: f"arn:aws:iam::123456789012:role/{k}" for k in SERVICIOS},
              "ecr": {k: f"123456789012.dkr.ecr.{REGION}.amazonaws.com/salome-{k}" for k in SERVICIOS}}
        for n, c in SERVICIOS.items():
            rep = ParamValidator().validate(parametros(n, c, tf, a.version, "123456789012", "https://x"), modelo)
            print(n, "parámetros válidos" if not rep.has_errors() else rep.generate_report())
        return
    tf = salidas_terraform()
    cuenta = boto3.client("sts").get_caller_identity()["Account"]
    existentes = {}
    for s in ecs.list_services(cluster="default").get("serviceArns", []):
        existentes[s.rsplit("/", 1)[-1]] = s
    url_modelos = None
    for nombre in ("ingesta", "modelos", "tablero"):  # tablero al final: necesita la URL de modelos
        p = parametros(nombre, SERVICIOS[nombre], tf, a.version, cuenta, url_modelos)
        if p["serviceName"] in existentes:
            p.pop("serviceName"); p.pop("infrastructureRoleArn"); p.pop("tags")
            r = ecs.update_express_gateway_service(serviceArn=existentes[f"salome-{nombre}"], **p)
            print("actualizado", nombre)
        else:
            r = ecs.create_express_gateway_service(**p)
            print("creado", nombre)
        conf = r["service"].get("activeConfigurations") or [{}]
        rutas = conf[0].get("ingressPaths", [])
        if rutas:
            print("  URL:", rutas[0]["endpoint"])
            if nombre == "modelos":
                url_modelos = rutas[0]["endpoint"].rstrip("/")
    print("Revisa el estado con: aws ecs describe-express-gateway-service --service-arn <arn>")


if __name__ == "__main__":
    sys.exit(main())
