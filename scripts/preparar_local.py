"""Crea en un entorno local (moto) el mismo bucket y las mismas colas que en AWS,
y aplica el esquema a un PostgreSQL local. Sirve para probar la tubería sin gastar.

    moto_server -p 5055 &
    export AWS_ENDPOINT_URL=http://localhost:5055 AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=x AWS_DEFAULT_REGION=us-east-2
    python scripts/preparar_local.py --db postgresql://postgres@localhost:5433/salome
"""
import argparse
import json
from pathlib import Path

import boto3
import psycopg2

RAIZ = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser()
ap.add_argument("--bucket", default="data-startup-salome-13454721")
ap.add_argument("--db", required=True)
a = ap.parse_args()

s3, sqs = boto3.client("s3"), boto3.client("sqs")
s3.create_bucket(Bucket=a.bucket, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
dlq = sqs.create_queue(QueueName="salome-pedidos-dlq", Attributes={"MessageRetentionPeriod": "1209600"})["QueueUrl"]
dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
cola = sqs.create_queue(QueueName="salome-pedidos", Attributes={
    "VisibilityTimeout": "120", "ReceiveMessageWaitTimeSeconds": "20", "MessageRetentionPeriod": "345600",
    "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})})["QueueUrl"]
print("QUEUE_URL=" + cola)
print("DLQ_URL=" + dlq)

with psycopg2.connect(a.db) as conn, conn.cursor() as cur:
    cur.execute((RAIZ / "infra/sql/esquema.sql").read_text())
print("esquema aplicado")
