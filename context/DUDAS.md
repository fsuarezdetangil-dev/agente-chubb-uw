# DUDAS — agente-chubb-uw

Registro de decisiones pendientes de confirmación con Chubb EMEA.

---

## DUDA-001 — Proveedor LLM: Anthropic directo vs Azure OpenAI

**Pregunta:** ¿Se usa la API de Anthropic directa o Azure OpenAI para la PoC?

**Decisión por defecto:** API de Anthropic directa con modelo `claude-sonnet-4-6`.

**Si Chubb requiere Azure OpenAI:**
1. Reemplazar `langchain-anthropic` por `langchain-openai` en requirements.txt
2. Actualizar `.env.example` con `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
3. Actualizar la inicialización del LLM en cada nodo

**Estado:** Pendiente confirmación — usando Anthropic por defecto

---

## DUDA-006 — LangSmith 403 / tracing de observabilidad

**Observación (sesiones 2026-06-30 y 2026-07-02):** Las claves de LangSmith de la cuenta personal Accenture-EU devolvían errores 403 al intentar activar tracing automático vía `LANGCHAIN_TRACING_V2=true`. El endpoint estándar (us) no era compatible con la cuenta EU.

**Resolución:** Migración completa de la capa de tracing/observabilidad a **Phoenix Arize** (2026-07-06). El harness de evaluación (datasets, experimentos) sigue en LangSmith porque es independiente del tracing en tiempo real.

**Archivos creados:**
- `observability/phoenix/init_tracing.py`
- `scripts/test_phoenix_connection.py`

**Estado:** RESUELTA — 2026-07-06. Tracing activo en app.phoenix.arize.com vía PHOENIX_API_KEY.

---

## DUDA-002 — Vector store: ChromaDB local vs cloud

**Pregunta:** ¿ChromaDB local es suficiente para la PoC o se prefiere un vector store cloud desde el inicio?

**Decisión por defecto:** ChromaDB local en `backend/kb/index/` para la PoC.

**Si se prefiere cloud (producción o PoC avanzada):**
- Opción recomendada: Azure Cognitive Search (ya en stack Chubb)
- Alternativa: Pinecone, Weaviate Cloud

**Estado:** ChromaDB local para PoC, reemplazar en producción

---

## DUDA-003 — Pricing tool: ¿existe una API interna?

**Pregunta:** ¿Chubb EMEA tiene una API de pricing certificada que podamos integrar en Node 4?

**Resolución:** No existe API interna de pricing para la PoC. Se implementará un stub que simula la llamada y respuesta de un motor de pricing real (inputs: datos del riesgo extraídos → outputs: prima técnica, desglose de coberturas, condiciones). El stub debe tener la misma firma que tendría una API real para facilitar la sustitución en producción.

**Estado:** RESUELTA — implementar stub en Fase 3D

---

## DUDA-004 - cnae_code y loss_history en ground-truth vs. email

**Observacion (Fase 3B):** El ground-truth incluye cnae_code y loss_history, pero estos campos no aparecen en el cuerpo del email — vienen en los adjuntos (cuestionario). Como el Node 2 no parsea adjuntos reales todavia, estos campos quedaran null hasta implementar pdf_parser.

**Impacto:** CA-02 accuracy penalizada artificialmente. Con adjuntos reales subira.

**Decision para PoC:** Aceptar que cnae_code se solicite via HITL-1 si no aparece en el email. No penalizar CA-02 por campos en adjuntos no parseados.

**Estado:** Registrado — revisar al implementar pdf_parser

---

## DUDA-005 — Contaminación de datos sintéticos entre email_raw y missing_fields_expected (14 submissions HITL-1)

**Observación (sesión 2026-07-02, investigación de HITL-1):** Se diagnosticó por qué HITL-1 nunca se activaba (0/14 en las pasadas E2E). La causa NO era la falta de `pdf_parser` (como se había documentado): era una **contaminación de los datos sintéticos**. En las 14 submissions con `expected_hitl_trigger = "HITL-1_datos_incompletos"`, el `ground_truth` marcaba correctamente ciertos campos como faltantes (`missing_fields_expected` solo contenía `requested_coverages` y/o `sum_insured_eur`, ambos campos de **email**, nunca cnae_code/loss_history/loss_ratio), pero el **cuerpo del email (`email_raw.body`) seguía conteniendo literalmente el valor de esos campos**. Ejemplo: SUB-063 tenía `sum_insured_eur = null` y `missing = ['sum_insured_eur']` en el ground truth, pero el email decía "…con una suma asegurada aproximada de 1.007.404 EUR". El LLM, correctamente, extraía la cifra → `missing_fields = []` → HITL-1 no se activaba.

Se descartó la hipótesis alternativa de "cifra aproximada = pedir confirmación": el 100% de los 72 emails (incluidos STP) usa la palabra "aproximada", así que no discrimina.

**Decisión y corrección aplicada:** El ground truth ya estaba bien; sobraba la información en el email. Se editó **únicamente** `email_raw.body` de las 14 submissions, eliminando o difuminando la frase que revelaba el campo marcado como missing (coberturas → "coberturas pendientes de confirmar"; suma → "suma asegurada pendiente de confirmar"). No se tocó `extracted_data_ground_truth`, `missing_fields_expected`, `expected_hitl_trigger` ni ningún otro campo. Se verificó que las frases editadas no contenían de paso `province` ni `activity_description` (no había fuga). Archivo afectado: `data/samples/submissions_synthetic_all_70.json`.

**Relación con DUDA-004:** distinta. DUDA-004 trata de campos de adjunto (cnae/loss_history) no parseados y su efecto en CA-02. DUDA-005 trata de la inconsistencia email↔ground_truth que bloqueaba HITL-1.

**Estado:** RESUELTA — datos corregidos 2026-07-02. `pdf_parser` queda descartado como solución a HITL-1.

---

## DUDA-007 — Contaminación paralela en `extracted_text_summary` de los adjuntos (10 submissions HITL-1)

**Observación (sesión 2026-07-08, al encender el parseo de adjuntos):** Hasta esta sesión, Node 2 no leía realmente el contenido de los adjuntos: `_format_attachments` en `extraction_node.py` leía la clave `description`, pero los adjuntos del dataset guardan el texto en `extracted_text_summary`. Es decir, el adjunto nunca llegaba al LLM (la extracción era 100% email). Al arreglar ese bug para habilitar el parseo, se encontró una contaminación de datos sintéticos **de la misma naturaleza que DUDA-005 pero en otro canal**: mientras que en DUDA-005 el valor marcado como faltante se filtraba por el `email_raw.body`, aquí se filtraba por el `extracted_text_summary` del adjunto.

Medición sobre las 72: los 14 casos `HITL-1_datos_incompletos` tienen su campo faltante presente en alguna fuente. En concreto, **10 de esos 14** tienen `sum_insured_eur` marcado como faltante en el ground truth (`sum_insured_eur = null`, y `sum_insured_eur ∈ missing_fields_expected`), pero el adjunto decía literalmente "Suma asegurada solicitada: <N> EUR". Como `sum_insured_eur` es campo de EMAIL (está en `CAMPOS_EMAIL` y por tanto afecta al routing de HITL-1), al empezar a leer el adjunto el LLM rellenaría ese valor → `missing_fields` dejaría de incluirlo → HITL-1 no se activaría en esos 10 → CA-06 regresaría (deshaciendo el fix del 2026-07-04 que llevó HITL-1 a 14/14).

Submissions afectadas (10): SUB-006, SUB-011, SUB-016, SUB-021, SUB-026, SUB-036, SUB-041, SUB-056, SUB-063, SUB-064. Los 4 restantes de los 14 HITL-1 (missing = solo `requested_coverages`: SUB-001, SUB-031, SUB-046, SUB-051) NO requieren limpieza: el adjunto nunca lista coberturas (0/72).

**Decisión y corrección aplicada:** El ground truth ya estaba bien; sobraba la cifra en el adjunto. Se editó **únicamente** el campo `extracted_text_summary` de esas 10 submissions, sustituyendo "Suma asegurada solicitada: <N> EUR." por "Suma asegurada solicitada: pendiente de confirmar.". El resto del texto del adjunto (CNAE, actividad, ubicación, histórico de siniestros, loss ratio) queda **intacto** — precisamente porque `cnae_code`, `loss_history` y `loss_ratio` SÍ queremos seguir extrayéndolos del adjunto (mejora de CA-02, ver DUDA-004). No se tocó `extracted_data_ground_truth`, `missing_fields_expected` ni ningún otro campo. Chequeo de fugas: la frase sustituida solo contenía la suma asegurada, ningún otro dato. Archivo afectado: `data/samples/submissions_synthetic_all_70.json`.

**Nota sobre `submissions_edge_cases_12.json`:** este archivo contiene copias de SUB-063 y SUB-064 con el adjunto aún sin limpiar. No se editó porque `scripts/upload_dataset.py` deduplica por `submission_id` cargando `_all_70.json` primero, así que las copias de edge_cases se descartan y el eval usa las versiones limpias. Quedan como copias latentes; limpiar si en el futuro se usa `edge_cases_12.json` de forma independiente.

**Cambios de código asociados (no de datos):** `_format_attachments` ahora lee `extracted_text_summary`; el prompt `extraction_node.md` indica explícitamente extraer `cnae_code`/`loss_history`/`loss_ratio` de la memoria adjunta. NO se tocó `_compute_missing_fields`, `CAMPOS_EMAIL` ni `CAMPOS_ADJUNTO`: el routing a HITL-1 sigue dependiendo solo de campos de email.

**Relación con DUDA-004 y DUDA-005:** complementa a ambas. DUDA-004 anticipaba que parsear adjuntos mejoraría CA-02 (cnae/loss_history/loss_ratio) — esta sesión lo materializa. DUDA-005 corrigió la contaminación email↔ground_truth; DUDA-007 es la misma inconsistencia pero en el canal adjunto↔ground_truth, que solo se manifestó al empezar a leer el adjunto de verdad.

**Estado:** RESUELTA — datos y código corregidos 2026-07-08. Pendiente confirmar a nivel agregado con la pasada de las 72 en LangSmith (no relanzada aún).
