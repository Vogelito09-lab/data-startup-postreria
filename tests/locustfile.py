"""Prueba de carga de la API de modelos (E3): 50 usuarios simultáneos.

    locust -f tests/locustfile.py --host https://salome-modelos....on.aws --headless -u 50 -r 5 -t 3m --csv docs/carga

Cada usuario simula a alguien abriendo el tablero: pide el pronóstico de venta y el de pasteles
enteros, y consulta si los próximos días serán fuertes. Espera de 1 a 3 segundos entre clics.
"""
import random
from datetime import date, timedelta

from locust import HttpUser, between, task

DIAS = [str(date(2026, 10, 31) + timedelta(days=i)) for i in range(1, 8)]


class Visitante(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def pronostico_venta(self):
        self.client.get("/pronostico?dias=14", name="/pronostico (venta)")

    @task(2)
    def pronostico_enteros(self):
        self.client.get("/pronostico?dias=7&serie=enteros", name="/pronostico (enteros)")

    @task(2)
    def clasificar(self):
        self.client.get(f"/clasificar?fecha={random.choice(DIAS)}", name="/clasificar")

    @task(1)
    def salud(self):
        self.client.get("/salud")
