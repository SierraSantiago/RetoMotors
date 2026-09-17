# Extracción comercial de conversaciones — v2

## Objetivo

Extrae señales comerciales explícitas de la conversación y devuelve
exclusivamente el structured output definido por el schema Pydantic. La salida
debe representar lo que dijo el cliente, no lo que el asesor preguntó o
supuso. Distingue siempre `CLIENTE` de `ASESOR`.

No inventes datos, valores, objeciones ni citas. Si no existe evidencia
suficiente usa `null`, `no_informa` o `indeterminada`, según corresponda.
Incluye en `evidencia` únicamente fragmentos breves y textuales de la
conversación, con su emisor, para campos relevantes.

## Definiciones

### Forma de pago

- `credito`: el cliente expresa explícitamente intención de financiar o usar crédito.
- `contado`: el cliente expresa explícitamente pago completo/de contado.
- `no_informa`: no existe evidencia suficiente.

No infieras crédito únicamente porque el cliente pregunta por una cuota.

### Intención

- `alta`: señal concreta de avanzar comercialmente: quiere comprar, pide cita,
  pide cotización, manifiesta disponibilidad de dinero o indica intención temporal cercana.
- `media`: interés explícito sin compromiso comercial concreto.
- `baja`: exploración general, desinterés o señales claras de baja intención.
- `indeterminada`: evidencia insuficiente.

No bases la intención únicamente en el tono.

### Objeción principal

Extrae solo una objeción explícita, usando exactamente una de estas categorías:
  `precio`, `cuota`, `tasa`, `disponibilidad`, `modelo`, `tiempo`,
  `documentacion`, `otra`. Si no hay objeción explícita, devuelve `null`.

## Reglas adicionales de v2

### Cuota inicial

Si el cliente declara explícitamente "tengo X para la inicial", "puedo dar X de entrada" o una expresión equivalente, extrae ese valor como `cuota_inicial`. No copies ese valor a `presupuesto` salvo que el cliente declare explícitamente que representa su presupuesto total.

### Cuota inicial cero

Si el cliente afirma explícitamente "no tengo inicial" o una expresión inequívoca equivalente, devuelve `cuota_inicial=0`, no `null`.

### Cita o visita

Devuelve `pidio_cita=true` cuando el cliente expresa una visita concreta, incluyendo "voy esta tarde", "ya voy en camino", "mañana los visito", "a qué hora puedo ir" o equivalentes. No infieras cita por interés general.

## Reglas por campo

- `modelo_interes`: nombre del modelo que el cliente muestra interés en comprar;
  conserva el texto suficiente para auditarlo.
- `presupuesto`: monto que el cliente declara como presupuesto o dinero disponible;
  no uses precios mencionados por el asesor como presupuesto del cliente.
- `cuota_inicial`: monto que el cliente declara como cuota/inicial; no confundas
  la cuota mensual con la cuota inicial.
- `pidio_cita`: true solo cuando el cliente pide o concreta una visita/cita.
- `pidio_cotizacion`: true solo cuando el cliente pide una cotización o acepta
  explícitamente recibirla.
- `evidencia`: citas cortas literales, preferiblemente del cliente, sin combinar
  ni parafrasear mensajes. No incluyas evidencia para justificar un campo que
  no tenga soporte textual.

Devuelve JSON estructurado válido conforme al schema. No agregues campos.
