# Reporte de limpieza

Registros de entrada: **25,074** · Registros limpios: **25,044**

| Tipo de error | Qué se encontró | Registros | Corrección |
|---|---|---:|---|
| Duplicados | Filas idénticas repetidas | 30 | Eliminadas |
| Formato | Nombre de producto en minúsculas o con espacios | 45 | Unificado al nombre oficial |
| Tipo de dato | Unidades escritas como texto ("2 pz") | 12 | Convertidas a número |
| Faltantes | Precio unitario vacío | 20 | Precio de catálogo del producto |
| Faltantes | Unidades vacías | 40 | Reconstruidas con total ÷ precio |
| Error lógico | Unidades negativas | 15 | Reconstruidas con total ÷ precio |
| Atípicos | Unidades imposibles (999) | 10 | Reconstruidas con total ÷ precio |
| Error lógico | Total ≠ unidades × precio | 20 | Total recalculado |
| Irrecuperables | Sin forma de reconstruir | 0 | Eliminados |
