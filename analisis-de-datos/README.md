# Salomé · Analítica de Datos (IAD-2403), proyecto integrador

Equipo: Jarom Cortes Pérez · Carlos Antonio Vogel Romero · Profesor: Armando Gallardo Heredia

Pregunta: ¿se puede saber dos días antes si un día va a pedir 2 o más pasteles enteros? (clasificación binaria, `dia_fuerte`).

| Entrega | Archivo |
|---|---|
| Avance 1 · Dataset y EDA | `Avance1_EDA_Salome.ipynb` |
| Avance 2 · Entrenamiento y comparativa | `Avance2_Modelos_Salome.ipynb` (incluye el EDA) |
| Entrega final · Notebook | `Final_Salome_Modelado_Predictivo.ipynb` (incluye los dos avances) |
| Entrega final · Reporte ejecutivo | `Reporte_ejecutivo_Salome.pdf` |

Los notebooks ya vienen ejecutados. Para volver a correrlos, abrirlos desde esta carpeta:

```bash
pip install -r requirements.txt
jupyter lab
```

```
datos/pedidos_salome_2020_2026.csv   archivo crudo de pedidos (2,627 renglones, con errores de captura)
datos/catalogo_precios.csv           precios de lista por fecha
datos/calendario_cierres.csv         días que no abrió (vacaciones y días sueltos)
datos/pedidos_salome_limpio.csv      lo genera el Avance 1 (sección 3.5)
datos/dias_salome.csv                tabla de modelado, una fila por día abierto (sección 5)
limpieza.py                          módulo de limpieza del proyecto (copia de services/worker/limpieza.py)
figuras/                             gráficas que usa el reporte
resultados_ad.json                   cifras de la entrega final
```
