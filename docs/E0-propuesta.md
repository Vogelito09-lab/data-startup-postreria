# E0 · Propuesta — DulceDato Analytics

**Proyecto Integrador DATA STARTUP** · Cómputo en la Nube (IAD-2408) × Analítica de Datos (IAD-2403)
Integrantes: Jarom Cortes Perez (Cloud Lead) · Carlos Antonio Vogel Romero (Data Lead)
Proveedor de nube: **AWS** (cuenta propia con el Plan gratuito) · Cliente: **Salomé** (postrería por pedido)

## 1. Resumen

**DulceDato Analytics** es un tablero con pronóstico para postrerías que venden por redes sociales. Cada
mañana le dice al negocio cuántas piezas preparar de cada postre a partir de sus propios pedidos, para
tirar menos producto y rechazar menos pedidos en los días fuertes.

Nuestro primer cliente es **Salomé**, una postrería **sin tienda física**: todos sus pedidos llegan por
**Instagram y WhatsApp** y se entregan a domicilio o se recogen.

## 2. Problema

En un negocio por pedido la venta no se ve en un mostrador: llega como mensajes, muchos de noche y a
veces para el mismo día. Varios postres (como el cheesecake) se preparan con anticipación porque
necesitan reposar, así que la producción se decide antes de saber cuántos pedidos llegarán:

- Si se prepara de más entre semana, sobra producto que dura 2 o 3 días refrigerado (**merma**).
- Si se prepara de menos para el fin de semana o fechas como San Valentín y el 10 de mayo, hay que
  **rechazar pedidos** o pedir al cliente que espere, y ese cliente compra en otro lado.
- Los pedidos quedan dispersos en dos chats, así que nadie sabe con números qué días, horas y productos
  le dejan más.

## 3. Entrevista

| Dato | Valor |
|---|---|
| Entrevistada | Dueña y encargada de producción de Salomé |
| Fecha y duración | 21 de octubre de 2026 · 20 minutos |

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Cómo decides cuánto preparar de cada postre cada día? | "Reviso los pedidos que ya tengo confirmados en WhatsApp e Instagram y lo que vendí los días anteriores. Decido la tarde anterior, porque el cheesecake tiene que reposar toda la noche, y en la mañana ajusto. Pero muchas veces es a ojo; no tengo un pronóstico." |
| 2 | ¿Cuánto se queda sin vender al final del día y qué haces con eso? | "En días tranquilos me sobran entre 8 y 15 rebanadas o piezas. Lo que aguanta lo ofrezco al día siguiente en historias y lo demás se retira. Calculo que pierdo entre $2,500 y $4,000 a la semana, pero no lo anoto." |
| 3 | ¿Qué días, horas o temporadas vendes más y menos? | "Viernes, sábado y domingo son los fuertes; entre semana es más tranquilo. Los mensajes llegan sobre todo en la noche, después de las 7. Sube mucho en San Valentín, Día de las Madres, graduaciones y diciembre, y también cuando hay quincena." |
| 4 | ¿Te ha pasado quedarte sin un postre que te piden? | "Sí, sobre todo el cheesecake clásico y el tres leches en fin de semana, unas dos o tres veces por semana. Algunos clientes cambian de sabor, otros lo piden para otro día y otros ya no contestan. No sé cuántos pedidos pierdo así." |
| 5 | Si una app te dijera cada mañana cuánto preparar de cada postre, ¿la usarías? ¿Cuánto pagarías? | "Sí, si es sencilla, me dice cantidades y puedo corregirlas cuando tengo pedidos especiales. Pagaría unos $499 al mes por un plan básico, si me demuestra que tiro menos y me quedo sin producto menos veces." |

**Lo que aprendimos:**

1. La producción se decide a ojo y con un día de anticipación; hace falta una estimación basada en el historial de pedidos.
2. La merma ($2,500 a $4,000 por semana) y los pedidos perdidos por falta de producto cuestan dinero, pero no se miden.
3. Los patrones por día de la semana, hora del mensaje, quincena y temporada pueden convertirse en cantidades concretas a preparar.

## 4. Cadena de preguntas

| Nivel | Pregunta |
|---|---|
| Negocio | ¿Cuánto preparo mañana de cada postre? |
| Analítica | ¿Cuántas unidades de cada producto se pedirán por día en los próximos 7 días, según el día de la semana, la temporada, la quincena y los pedidos anteriores? |
| Variable a predecir | `unidades` pedidas por fecha y producto (unidades/día, horizonte de 1 a 7 días) |

Pregunta secundaria para el clasificador de E3: ¿mañana será un día de demanda alta?

## 5. Lean Canvas

| Bloque | Contenido |
|---|---|
| **Problema** | 1) Producción decidida a ojo antes de que lleguen los pedidos. 2) Merma entre semana y pedidos rechazados en días fuertes. 3) Pedidos dispersos en Instagram y WhatsApp, sin números. |
| **Segmento de clientes** | Postrerías y reposterías caseras o sin local que venden por redes sociales; después, cafeterías y panaderías pequeñas. Primer cliente: Salomé. |
| **Propuesta de valor** | "Cada mañana sabes cuánto preparar de cada postre." Menos desperdicio y menos pedidos perdidos, sin saber de datos. |
| **Solución** | Carga de pedidos (CSV o formulario), tablero que se entiende en 30 segundos y pronóstico diario por producto. |
| **Canales** | Instagram y WhatsApp (los mismos donde está el cliente), demostraciones del tablero, recomendación entre negocios y proveedores de insumos de repostería. |
| **Fuentes de ingreso** | Suscripción mensual de $499 MXN (precio de la entrevista); freemium: tablero gratis y pronóstico en el plan de pago. |
| **Estructura de costos** | Nube (capa gratuita durante el proyecto), dominio, soporte y captura inicial de los pedidos. |
| **Métricas clave** | Merma semanal, pedidos rechazados por falta de producto, error del pronóstico (MAE), negocios activos. |
| **Ventaja injusta** | Enfoque en negocios que venden por redes y no por mostrador, y modelo ajustado a fechas mexicanas (quincena, 10 de mayo, graduaciones, diciembre). |

## 6. Inventario de datos

| Concepto | Detalle |
|---|---|
| Fuente | Historial de pedidos de Salomé por Instagram y WhatsApp, exportado a CSV |
| Columnas | `pedido_id`, `fecha`, `hora`, `producto`, `categoria`, `unidades`, `precio_unitario`, `total`, `canal` (Instagram/WhatsApp), `entrega` (domicilio/recoger), `metodo_pago` |
| Periodo | 1-abr-2025 a 30-sep-2026 (18 meses de datos diarios) |
| Volumen | 25,074 registros · 17,366 pedidos (supera el mínimo de 12 meses y 5,000 registros) |
| Granularidad | Un renglón por producto dentro de cada pedido (un pedido con 2 productos ocupa 2 renglones) |
| Privacidad | Sin nombres, teléfonos, usuarios de Instagram ni direcciones de clientes; si vienen en los datos reales se eliminan antes de subirlos (LFPDPPP). |

**Diccionario de datos**

| Columna | Tipo | Significado | Ejemplo |
|---|---|---|---|
| `pedido_id` | entero | Número de pedido; se repite si el pedido trae varios productos | 5021 |
| `fecha` | fecha | Día en que se hizo el pedido | 2026-05-09 |
| `hora` | hora | Hora en que llegó el mensaje del pedido | 21:14 |
| `producto` | texto | Postre pedido | Cheesecake clásico (rebanada) |
| `categoria` | texto | Grupo del producto: Rebanadas, Galletas y brownies, Pasteles enteros | Rebanadas |
| `unidades` | entero | Piezas de ese producto en el pedido | 2 |
| `precio_unitario` | decimal (MXN) | Precio de una pieza | 75.00 |
| `total` | decimal (MXN) | `unidades × precio_unitario` | 150.00 |
| `canal` | texto | Por dónde llegó el pedido: Instagram o WhatsApp | WhatsApp |
| `entrega` | texto | Domicilio o Recoger | Domicilio |
| `metodo_pago` | texto | Transferencia o Efectivo | Transferencia |

## 7. Arranque técnico

**Proveedor elegido: AWS.** Se revisó su capa gratuita: las cuentas nuevas con el **Plan gratuito** reciben créditos y
no generan cargos mientras no se cambie a un plan de pago; el plan dura 6 meses o hasta agotar los créditos. Cubre lo que
usa el proyecto: S3 para el data lake y una instancia EC2 `t3.micro` para el tablero.

| Elemento | Estado | Evidencia |
|---|---|---|
| Cuenta de AWS con el Plan gratuito (sin cargos mientras no se cambie de plan), región `us-east-2` (Ohio) | ✅ | ![Plan gratuito](img/aws-plan-gratuito.png) |
| Alerta de presupuesto de gasto cero en AWS Budgets (avisa por correo desde el primer dólar) | ✅ | ![Presupuesto](img/aws-presupuesto.png) |
| Un acceso por integrante: cada uno entra con su propio AWS Builder ID; Jarom fue invitado como miembro del equipo. No se usa una cuenta raíz con contraseña compartida | ✅ | ![Equipo](img/aws-equipo.png) |
| Repositorio en GitHub con ambos integrantes | ✅ | https://github.com/Vogelito09-lab/data-startup-postreria |
| Estructura inicial del repositorio | ✅ | Ver README |

## 8. Uso de IA generativa

- **ChatGPT:** apoyo para preparar la entrevista y estructurar la propuesta.
- **Claude:** formato de entrevista, código del generador de datos, limpieza y tablero, y redacción de este documento.

