# CHUBB EMEA — COMMERCIAL LINES PRICING GUIDELINES
## Property & Casualty — Documento Sintético para PoC

**Clasificación:** Uso interno — Knowledge Base sintética para PoC del P&C Underwriting Agent
**Versión:** v1.0 — Junio 2026
**Ámbito:** Hub Madrid · Commercial Lines · Riesgos estándar (renovación y new business)
**Nota:** Este documento contiene rangos de tasa y condicionado sintéticos generados para la PoC. No refleja tarifas reales de Chubb. Su único propósito es servir como contenido de knowledge base para que el retriever RAG del Node 4 (Risk Assessment) tenga material real sobre el que operar. La cifra de prima final en cualquier caso real debe generarse exclusivamente mediante la herramienta de pricing certificada — este documento solo orienta rangos indicativos para el agente, no sustituye dicha herramienta.

---

## SECCIÓN 1 — PRINCIPIOS GENERALES DE PRICING

### 1.1 Rol de este documento en la arquitectura

Este documento alimenta el RAG del Node 4 para que el agente pueda recuperar el rango de tasa aplicable y el condicionado estándar antes de invocar la herramienta certificada `pricing_tool_certified()`. El agente nunca debe calcular ni afirmar una cifra de prima final a partir de este documento — solo puede usarlo para informar los parámetros de entrada de la herramienta certificada y para justificar al underwriter por qué un rango de tasa es razonable.

### 1.2 Estructura de la tasa técnica

La tasa técnica (rate) se expresa como porcentaje (‰ o %) de la suma asegurada o del límite de indemnización, y varía según: línea de negocio, código CNAE, factor de siniestralidad histórica (loss ratio), y factores de agravación específicos identificados por el `risk_scoring_engine()`.

---

## SECCIÓN 2 — RANGOS DE TASA TÉCNICA — PROPERTY

### 2.1 Tasas base por actividad (en ‰ anual sobre suma asegurada)

| CNAE | Actividad | Tasa base mínima | Tasa base máxima | Notas |
|---|---|---|---|---|
| 1071 | Panadería industrial | 1.8‰ | 2.6‰ | Aplicar recargo de 0.3‰ si no hay sistema de detección de incendios certificado |
| 7022 | Consultoría / oficinas | 0.6‰ | 1.0‰ | Tasa más baja del catálogo — riesgo de incendio mínimo |
| 5210 | Almacén logístico | 1.5‰ | 2.4‰ | Recargo de 0.4‰ por encima de 3M EUR de suma asegurada por concentración de valor |
| 2511 | Carpintería metálica | 1.4‰ | 2.0‰ | — |
| 6910 | Despachos profesionales | 0.6‰ | 1.0‰ | — |
| 6311 | Data center | 1.2‰ | 1.8‰ | Descuento de 0.2‰ si dispone de redundancia eléctrica N+1 documentada |
| 5510 | Hotel urbano | 1.6‰ | 2.3‰ | Evaluar conjuntamente con tasa de RC de explotación |
| 3109 | Fabricación de muebles | 2.0‰ | 2.8‰ | Tasa elevada por riesgo de incendio de materiales combustibles |
| 4711 | Supermercado | 1.0‰ | 1.6‰ | — |
| 8623 | Clínica dental | 0.8‰ | 1.3‰ | — |
| 2222 | Envases de plástico (revisión) | 2.8‰ | 4.0‰ | Tasa elevada — requiere aprobación de underwriter senior |
| 4675 | Almacén productos químicos (revisión) | 3.0‰ | 4.5‰ | Tasa elevada — requiere aprobación de underwriter senior |
| 1310 | Textil maquinaria antigua (revisión) | 2.5‰ | 3.8‰ | Recargo si no hay informe de inspección eléctrica reciente |

### 2.2 Descuentos admisibles — Property

- **Descuento por sistema de protección contra incendios certificado (sprinklers + detección):** hasta 15% sobre la tasa base.
- **Descuento por fidelización (cliente renovación sin siniestros en 3 años):** hasta 10% sobre la tasa base.
- **Descuento por franquicia incrementada (a elección del cliente):** hasta 8% adicional, sujeto a aprobación de underwriter.

Ningún descuento acumulado puede superar el 25% sobre la tasa base sin aprobación explícita de un underwriter senior.

---

## SECCIÓN 3 — RANGOS DE TASA TÉCNICA — CASUALTY / LIABILITY

### 3.1 Tasas base por actividad (en ‰ anual sobre límite de indemnización)

| CNAE | Actividad | Tasa base mínima | Tasa base máxima | Notas |
|---|---|---|---|---|
| 4321 | Instalaciones eléctricas | 2.0‰ | 3.0‰ | — |
| 7112 | Ingeniería civil | 1.8‰ | 2.8‰ | Evaluar RC Profesional de forma separada si aplica |
| 8121 | Limpieza industrial | 1.5‰ | 2.2‰ | — |
| 9311 | Gimnasios | 2.2‰ | 3.2‰ | Descuento si hay protocolos de seguridad auditados |
| 5610 | Restaurantes | 1.8‰ | 2.6‰ | — |
| 3312 | Mantenimiento de ascensores | 2.5‰ | 3.5‰ | Tasa elevada por naturaleza de la actividad |
| 7111 | Arquitectura | 1.6‰ | 2.4‰ | — |
| 8559 | Academias de formación | 1.0‰ | 1.6‰ | — |
| 8130 | Jardinería y paisajismo | 1.4‰ | 2.0‰ | — |
| 8010 | Seguridad privada (revisión) | 3.5‰ | 5.0‰ | Tasa elevada — requiere aprobación de underwriter senior |
| 9001 | Eventos y espectáculos (revisión) | 3.0‰ | 4.5‰ | Variable según tipo de evento — solicitar detalle |
| 4941 | Transporte de mercancías (revisión) | 3.2‰ | 4.8‰ | Evaluar antigüedad de flota |
| 8621 | Cirugía estética (revisión) | 4.0‰ | 6.0‰ | Tasa más elevada del catálogo Casualty — riesgo de RC Profesional médica |

### 3.2 Descuentos admisibles — Casualty

- **Descuento por protocolos de seguridad documentados y auditados:** hasta 12% sobre la tasa base.
- **Descuento por fidelización (renovación sin siniestros):** hasta 10% sobre la tasa base.
- **Recargo obligatorio por siniestralidad:** si el loss ratio histórico está entre 0.45 y 0.85 (rango "requiere revisión" según appetite guidelines), aplicar recargo de entre 15% y 30% sobre la tasa base, a definir por el underwriter senior en el HITL correspondiente.

---

## SECCIÓN 4 — CONDICIONADO ESTÁNDAR

### 4.1 Condicionado base — Property

Toda póliza de Property estándar dentro de apetito incluye como condicionado base: franquicia mínima de 500 EUR por siniestro, cobertura de daños materiales por incendio, agua, robo y fenómenos atmosféricos, y exclusión estándar de desgaste, vicio propio y falta de mantenimiento.

### 4.2 Condicionado base — Casualty

Toda póliza de Casualty / Liability estándar dentro de apetito incluye como condicionado base: límite de indemnización por siniestro y agregado anual, sublímite específico para daños morales (10% del límite principal), y exclusión estándar de actos dolosos e incumplimiento normativo conocido y no corregido.

### 4.3 Condicionado adicional para casos "Requiere revisión"

Las submissions clasificadas como "Requiere revisión" en las appetite guidelines deben incorporar, además del condicionado base, una cláusula de revisión de siniestralidad a los 12 meses y, cuando proceda, un sublímite reducido específico para el factor de riesgo identificado (por ejemplo, sublímite de RC Productos en casos de fabricación, o franquicia incrementada en casos de siniestralidad histórica moderada).

---

## SECCIÓN 5 — REGLA DE INVOCACIÓN DE LA HERRAMIENTA CERTIFICADA

El agente debe seguir esta secuencia obligatoria en el Node 4:

1. Recuperar mediante RAG el rango de tasa base aplicable a la actividad (Secciones 2 o 3 de este documento).
2. Recuperar los descuentos o recargos admisibles según los factores identificados por `risk_scoring_engine()`.
3. Invocar `pricing_tool_certified()` pasando como parámetros: línea de negocio, suma asegurada o límite, rango de tasa recuperado, y factores de ajuste identificados.
4. La cifra de prima técnica final es exclusivamente la que devuelve `pricing_tool_certified()`. El agente no debe presentar al underwriter ninguna cifra de prima que no provenga de esta herramienta.

Esta secuencia es el control regulatorio no negociable bajo Solvencia II descrito en el Checklist Regulatorio (Control 2): ninguna cifra de pricing se genera por estimación del LLM.

---

*Fin del documento. Knowledge base sintética — KB-2 Pricing & Conditions — PoC P&C UW Agent Chubb EMEA.*
