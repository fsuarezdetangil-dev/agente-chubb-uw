# SESSION_LOG — agente-chubb-uw

Registro cronológico de sesiones de trabajo. Añadir una entrada al inicio de cada sesión nueva.

---

## Sesión 2026-07-08 (tarde) — EDD v2.0: análisis de fallos y mejoras de prompts

**Objetivo:** Analizar los fallos del baseline `e2e-v1-baseline-traced` (68 runs) e implementar mejoras en `backend/prompts/` para superar los umbrales CA-01 ≥ 95% y CA-06 ≥ 95%.

**Análisis de fallos (script Python sobre CSV baseline):**

- **CA-01** (LOB accuracy): 6 fallos detectados. Patrón: el `intake_node` sobreescribía la LOB declarada en el estado inicial por ambigüedad del email (consultoría → classified como casualty cuando era property, retail → classified como property cuando era casualty). Root cause: el prompt no daba prioridad explícita a la "Línea declarada".
- **CA-06** (HITL routing): 19 fallos detectados (más de los 7 estimados por la métrica de 72 runs, porque el baseline solo tiene 68 de 72):
  - **Cluster A (13 casos STP):** `hitl_point_3` disparado en submissions limpias con risk_score 60-70. Root cause: `_has_critical_flags()` en `risk_node.py` detecta keywords como "siniestros" en flags informativos/favorables generados por el LLM (ej. "sin siniestros en 3 años"). El prompt no prohibía incluir datos favorables en `risk_flags`.
  - **Cluster B (5 casos HITL-1 perdido):** campos faltantes (`sum_insured_eur`, `loss_history`) no detectados de forma consistente. El prompt de extracción no priorizaba ni ordenaba los campos críticos.
  - **Cluster C (1 caso HITL-3 perdido):** riesgo multinacional/multi-ubicación no reconocido como criterio de escalación.

**Cambios realizados (solo `backend/prompts/`):**

- **`intake_node.md` (H1):** Añadida regla de prioridad LOB: si "Línea declarada" no está vacía, respetarla a menos que el email la contradiga explícitamente. Ambigüedad → conservar LOB declarada con confidence "medium". También enriquecida la lista de coberturas de referencia (RC explotación en casualty, pérdida de beneficios en property).
- **`risk_node.md` (H2+H3):** (H2) Añadida instrucción explícita: `risk_flags` solo recoge factores negativos reales; nunca datos favorables, ausentes, ni informativos. (H3) Añadido criterio HITL-3: operación multinacional/multi-ubicación sin endorsement territorial.
- **`extraction_node.md` (H4):** Reescrita la instrucción de `missing_fields` con lista ordenada de 5 campos críticos con prioridad explícita y regla clara: si el campo tiene valor (no null, no array vacío), nunca incluirlo en missing_fields.

**Impacto esperado (sin validar aún — pendiente de relanzar evals):**

| CA | Baseline | Esperado v2.0 | Umbral |
|----|----------|--------------|--------|
| CA-01 | 89% (6 fallos) | ~97-100% | ≥ 95% |
| CA-06 | ~72% (19 fallos) | ~92-96% | ≥ 95% |

**Pendiente:** Relanzar `python scripts/run_phoenix_eval.py --name e2e-v2-prompt-fixes` en red corporativa para validar hipótesis y publicar como segundo experimento en Phoenix Datasets & Experiments.

---

## Sesión 2026-07-08 — Parseo real de adjuntos (CA-02) + bandeja de HITL pendientes

**Objetivo:** Dos piezas funcionales pedidas por el cliente: (A) que Node 2 lea de verdad el contenido de los adjuntos, y (B) un mecanismo consultable para saber qué submissions están esperando en un punto HITL.

**Parte A — Parseo de adjuntos:**

- **Bug encontrado:** `_format_attachments` en `extraction_node.py` leía la clave `description`, pero los adjuntos del dataset guardan el texto en `extracted_text_summary`. Es decir, hasta ahora el contenido del adjunto **nunca llegaba al LLM** (la extracción era 100% email). Corregido para leer `extracted_text_summary` (con fallback a `description`/`name`).
- **Contaminación paralela descubierta (DUDA-007):** al encender el parseo, se detectó que 10 de las 14 submissions HITL-1 tenían el `sum_insured_eur` (marcado como faltante en el ground truth) revelado literalmente en el `extracted_text_summary` del adjunto. Misma naturaleza que DUDA-005 (que se corrigió en el email), pero en el canal del adjunto. Sin limpiar, el LLM habría rellenado la suma → HITL-1 no se activaría → regresión de CA-06.
- **Corrección de datos:** editado ÚNICAMENTE el campo `extracted_text_summary` de esas 10 submissions (SUB-006, 011, 016, 021, 026, 036, 041, 056, 063, 064), sustituyendo "Suma asegurada solicitada: <N> EUR." por "Suma asegurada solicitada: pendiente de confirmar.". CNAE, actividad, siniestros y loss ratio quedan intactos (se quieren seguir extrayendo). No se tocó `extracted_data_ground_truth` ni `missing_fields_expected`. Chequeo de fugas OK; JSON revalidado; 62/72 adjuntos conservan suma numérica (72−10). Archivo: `data/samples/submissions_synthetic_all_70.json`. Nota: `submissions_edge_cases_12.json` tiene copias de SUB-063/064 sin limpiar, pero `upload_dataset.py` las deduplica, así que el eval usa las limpias.
- **Prompt:** `extraction_node.md` ahora indica explícitamente extraer `cnae_code`/`loss_history`/`loss_ratio` de la memoria de actividad adjunta.
- **No tocado:** `_compute_missing_fields`, `CAMPOS_EMAIL`, `CAMPOS_ADJUNTO` — el routing a HITL-1 sigue dependiendo solo de campos de email.

**Parte B — Bandeja de HITL (backend + diseño para frontend):**

- **`backend/agent/hitl_inbox.py`** (nuevo): función read-only `list_pending_hitl()` que enumera los `thread_id` del checkpointer SQLite, filtra submissions reales por convención de nombre (`^SUB-\d+$`, excluye threads de test como `-e2e`/`-px`/`-3B`), consulta `graph.get_state()` y devuelve las que tienen `.next` en un `hitl_point_*`. Cada item trae submission_id, hitl_point, company_name, line_of_business, broker, waiting_reason, thread_id, y los campos específicos del punto (missing_fields / appetite_verdict / risk_score+flags). Sin infraestructura en tiempo real: pensado para polling (los HITL esperan a una persona).
- **`scripts/list_pending_hitl.py`** (nuevo): CLI que imprime la bandeja agrupada por punto HITL.
- Sin dependencias nuevas (no se añadió FastAPI todavía, según lo acordado).

**Validación local (BD temporal, sin tocar checkpoints.db real ni LangSmith):**

- *Detección HITL:* SUB-063 (HITL-1, adjunto limpiado), SUB-003 (HITL-2 fuera), SUB-019 (HITL-3 score 85) → los 3 se pausan en su punto correcto y `list_pending_hitl()` los detecta con datos completos. 3/3.
- *CA-06 (16 submissions):* **14/14 HITL-1 se pausan en `hitl_point_1`** (incluidos los 10 con adjunto limpiado), 2/2 STP llegan a END sin HITL. Fix de HITL-1 preservado, sin regresión.
- *CA-02 (16 submissions):* `cnae_code` extraído y coincidente con adjunto 16/16; `loss_ratio` 16/16; `loss_history` 13/16 (los 3 restantes son casos de 0 siniestros → `[]`, correcto). Antes estos 3 campos quedaban null.

**Pendiente:** relanzar las 72 en LangSmith para confirmar a nivel agregado el efecto sobre CA-02 (esperado al alza) y verificar que CA-06 no baja. **No relanzado esta sesión** (a la espera de petición explícita). Frentes CA-01 (LOB) y CA-06 (fallos residuales en STP/HITL-3) siguen abiertos y no se tocaron.

---

## Sesión 2026-07-06 — Migración de observabilidad LangSmith → Phoenix Arize

**Objetivo:** Migrar la capa de tracing/observabilidad a Phoenix Arize sin tocar el agente ni los evals.

**Trabajo realizado:**

- **`requirements.txt`**: añadidas 3 dependencias Phoenix (`arize-phoenix-otel`, `openinference-instrumentation-langchain`, `opentelemetry-sdk`). `langsmith` conservada para el harness de evaluación.
- **`.env.example`**: añadidas variables `PHOENIX_API_KEY`, `PHOENIX_PROJECT_NAME`, `PHOENIX_COLLECTOR_ENDPOINT`. `LANGCHAIN_TRACING_V2` comentada; variables LangSmith EU conservadas (solo para evals).
- **`observability/phoenix/init_tracing.py`**: nuevo inicializador con `register()` de `phoenix.otel` + `LangChainInstrumentor`. Instrumenta LangChain/LangGraph globalmente sin tocar `backend/agent/`. Guard `_TRACING_INITIALIZED` evita doble init.
- **`observability/langsmith/README_archived.md`**: documenta que `setup_langsmith.py` queda archivado.
- **`scripts/run_e2e.py`**: añadido `load_dotenv()` + `init_tracing()` al inicio, antes del primer `graph.invoke()`.
- **`scripts/test_phoenix_connection.py`**: nuevo script de verificación (CA-01 Phoenix). Inicializa el tracer, envía span `setup-verification` y hace `force_flush`.
- **`context/DUDAS.md`**: cerrada DUDA-006 (LangSmith 403 → resuelta con migración a Phoenix).

**Criterios de aceptación:**
- CA-01: `python scripts/test_phoenix_connection.py` — pendiente de ejecutar con PHOENIX_API_KEY real.
- CA-02: traza visible en app.phoenix.arize.com → proyecto agente-chubb-uw — pendiente.
- CA-03: no hay referencias activas a `LANGCHAIN_TRACING_V2` ni imports `langsmith` en código de tracing — cumple.
- CA-04: `.env.example` actualizado con variables PHOENIX_* — cumple.
- CA-05: este log refleja la migración — cumple.

**Restricciones respetadas:**
- `backend/agent/`, `backend/tools/`, `evals/` — no modificados.
- `.env` con valores reales — no commiteado.
- Sin dependencias sin justificar (las 3 están justificadas en requirements.txt).

**Validación E2E con Phoenix activo** (72/72 submissions, sin errores, ~33 min):

| CA | LangSmith d1881dca | Phoenix (2026-07-07) | Umbral | Estado |
|---|---|---|---|---|
| CA-01 LOB accuracy | 90.3% | 89% | ≥95% | Pendiente |
| CA-02 Extracción | 99.1% | 99% | ≥80% | Cumple |
| CA-03 Missing fields | 100% | 100% | ≥90% | Cumple |
| CA-04 Appetite | 91.7% | 92% | ≥85% | Cumple |
| CA-05 RAG citas | 100% | 100% | 100% | Cumple |
| CA-06 HITL routing | 90.3% | 90% | ≥95% | Pendiente |
| CA-07 LLM-Judge | 100% | 100% | ≥85 en ≥90% | Cumple |
| CA-08 Time-to-quote | 100% | 100% | <4min | Cumple |

Sin regresiones respecto a LangSmith. 6/8 CAs cumplen umbral — igual que antes de la migración.

**Warning cosmético:** `OpenInferenceTracer.on_interrupt/on_resume` — incompatibilidad de versión entre `openinference-instrumentation-langchain` y la API de callbacks de LangGraph HITL. No bloquea la ejecución. Pendiente de resolución en versión futura del instrumentador o pin de versión compatible.

**Criterios de aceptación de la migración Phoenix:**
- CA-01 (test_phoenix_connection.py): CUMPLE — traza `setup-verification` visible en app.phoenix.arize.com
- CA-02 (trazas en Phoenix): CUMPLE — trazas E2E visibles en proyecto `agente-chubb-uw`
- CA-03 (sin referencias LangSmith en tracing): CUMPLE
- CA-04 (.env.example actualizado): CUMPLE
- CA-05 (SESSION_LOG): CUMPLE

**Sesión 2026-07-08 — Datasets & Experiments en Phoenix + fix trace_id:**

- Creados `scripts/upload_phoenix_dataset.py` y `scripts/run_phoenix_eval.py`.
- Primera pasada `e2e-baseline-phoenix` ejecutada (72/72, ver CSV exportado de Phoenix).
- Fix: `run_submission()` envuelve `graph.invoke()` en span manual OTEL para capturar `trace_id` y enlazarlo al experiment run → tokens y latencia visibles en Phoenix.
- Concepto golden dataset aclarado: las 72 submissions sintéticas + ground truth verificado a mano son el benchmark. En producción se sustituirán por casos reales validados por UWs senior.
- Enfoque EDD confirmado para v2.0: medir → analizar fallos → hipótesis → cambio → medir.

**Próxima acción:** investigar causa raíz de CA-01 (7 fallos LOB) y CA-06 (7 fallos HITL routing) para v2.0.

---

## Sesión 2026-07-04 — Fix de medición CA-03 + pasada final LangSmith (continuación de 2026-07-02)

**Objetivo:** Cerrar el trabajo iniciado el 2026-07-02: investigar por qué HITL-1 nunca se activaba (0/14), corregir el artefacto de medición de CA-03, y obtener una pasada final limpia de las 72 submissions en LangSmith.

**Fix de datos sintéticos (HITL-1 → CA-06):**
Investigación sobre `extraction_node.py`, datos sintéticos y evaluador CA-06 demostró que la causa raíz no era la falta de `pdf_parser` (diagnóstico anterior incorrecto — ver corrección en la entrada 2026-07-02 y DUDA-005). Los `missing_fields_expected` de las 14 submissions HITL-1 solo contenían `requested_coverages` y/o `sum_insured_eur`, pero el cuerpo del email incluía esos valores literalmente. Fix: editar `email_raw.body` de las 14 submissions (solo ese campo) eliminando la frase que revelaba el valor marcado como faltante. Validación local: 14/14 activaban `hitl_point_1`. Dataset re-subido a LangSmith (`chubb-uw-golden-72`). Pasada E2E `chubb-uw-e2e-d7973ef5`: CA-06 sube de 69.4% a 90.3% (HITL-1: 0/14 → 14/14; STP/HITL-2/3 sin regresión).

**Fix de medición CA-03 (artefacto del harness, no del agente):**
CA-03 seguía midiendo 80.6% en LangSmith pese a validación local 14/14. Causa: `_resume_hitl()` en `run_langsmith_eval.py` inyecta `missing_fields = []` al reanudar HITL-1 (simula al UW resolviendo los campos), y `eval_ca03` leía ese estado posterior, no el valor real detectado en extracción. Fix (solo evaluación, cero cambios en el agente):
- `backend/agent/state.py`: nuevo campo `missing_fields_at_extraction` (informativo, no cambia routing).
- `scripts/run_langsmith_eval.py`: captura `snapshot.values["missing_fields"]` en `missing_fields_at_extraction` antes de vaciarlo.
- `evals/evaluators.py`: `eval_ca03` y `langsmith_ca03` leen el campo nuevo con fallback a `missing_fields` (preserva comparabilidad con pasadas anteriores).
Validación local 14/14 OK con la ruta completa (grafo + resume + evaluador).

**Incidencias operativas durante el relanzamiento (documentadas para futuras sesiones):**
- **Pasada `ab609aaa` cortada a 41/72:** la causa no fue el standby timer (ya estaba en 0), sino el "lid close action" en AC que seguía en "Suspender" (0x1). Fix: `powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0` antes de lanzar; restaurar a 1 al terminar.
- **Error SSL intermitente tras suspensión:** al reanudar tras un cierre de tapa, el proxy corporativo de Accenture presentaba un certificado self-signed que el bundle SSL del venv no reconocía. Fix: bundle CA combinado (certifi + certificados raíz de Accenture exportados del almacén de Windows vía PowerShell/X509Store) pasado como `REQUESTS_CA_BUNDLE` solo para el proceso del eval. Los dos certificados raíz de Accenture están en el almacén Windows "Root" (CN=Accenture Internal Root CA y CN=Accenture Root CA).
- **Dato parcial útil:** los 41/72 de `ab609aaa` ya mostraban CA-03 = 100%, confirmando el fix antes de completar la pasada.

**Resultado final verificado** (experimento LangSmith `chubb-uw-e2e-d1881dca`, 72/72 sin errores, ~32 min):

| CA | Anterior (80b0e41d) | Final (d1881dca) | Umbral | Estado |
|---|---|---|---|---|
| CA-01 LOB accuracy | 91.7% | 90.3% | ≥95% | Pendiente |
| CA-02 Extracción | 96.8% | 99.1% | ≥80% | Cumple |
| CA-03 Missing fields | 80.6% | 100% | ≥90% | Cumple (cerrado hoy) |
| CA-04 Appetite | 91.7% | 91.7% | ≥85% | Cumple |
| CA-05 RAG citas | 100% | 100% | 100% | Cumple |
| CA-06 HITL routing | 69.4% | 90.3% | ≥95% | Pendiente |
| CA-07 LLM-Judge | 100% | 100% | ≥85 en ≥90% | Cumple |
| CA-08 Time-to-quote | 100% | 100% | <4min en ≥95% | Cumple |

6 de 8 CA cumplen umbral. CA-01 (7 fallos de 72) y CA-06 (7 fallos, todos en STP y HITL-3 — HITL-1 y HITL-2 ya al 100%) quedan pendientes sin causa raíz investigada; candidatos para la siguiente sesión.

---

## Sesión 2026-07-02 — Conexión LangSmith (cuenta Nicolás) + diagnóstico y corrección de CA-06/CA-07

**Objetivo:** Conectar el proyecto a LangSmith (cuenta de Nicolás, proyecto `agente-chubb-uw-nicolas`, workspace EU) y diagnosticar/corregir la caída de CA-06 y CA-07 detectada en la primera pasada E2E completa.

**Bugs encontrados y corregidos (orden cronológico):**
- **a) Contrato roto entre `upload_dataset.py` y `run_langsmith_eval.py`:** la referencia (ground truth) se subía en `outputs` pero se leía desde `inputs["__reference"]`. Fix: duplicarla también en `inputs` al subir el dataset.
- **b) `LANGSMITH_API_KEY` nueva daba 403:** la cuenta está en la región **EU** de LangSmith, que requiere endpoint distinto. Fix: añadir `LANGCHAIN_ENDPOINT` y `LANGSMITH_ENDPOINT` = `https://eu.api.smith.langchain.com` al `.env`.
- **c) Desalineación de nombre de variable:** el `.env` tenía `AZURE_OPENAI_DEPLOYMENT_ID` pero `backend/utils/llm.py` espera `AZURE_OPENAI_DEPLOYMENT`. Fix: renombrar en `.env`.
- **d) `run_langsmith_eval.py` crasheaba al imprimir el resumen final** (`AttributeError: 'dict' object has no attribute 'evaluation_results'`) por incompatibilidad con la versión instalada del SDK `langsmith` (0.9.4, que devuelve dicts al iterar en vez de objetos). Fix: la función de resumen ahora soporta ambas formas (dict y objeto).
- **e) Entorno de ejecución roto:** faltaba el paquete `langgraph-checkpoint-sqlite` y el Python global (3.14) tenía langchain/langgraph en versiones 1.x, muy por encima de lo que el código espera (0.2/0.3). Fix: venv aislado con Python 3.14 en una ruta corta fuera de OneDrive (`C:\Users\nicolas.renedo\AppData\Local\cv`), con `requirements.txt` instalado ahí.
- **f) CA-01 (LOB accuracy) medía sistemáticamente 0%** en todas las pasadas: falso negativo del harness, no fallo del agente. `upload_dataset.py` no incluía `line_of_business` en `OUTPUT_KEYS`, así que la referencia que leía el evaluador siempre era `None`. Fix: añadir `line_of_business` a `OUTPUT_KEYS` y volver a subir el dataset.
- **g) CA-06 (HITL routing) colapsaba a 43%** en la primera pasada E2E completa (frente al 73% de una pasada local anterior con muestra pequeña). Causa raíz identificada con evidencia cuantitativa sobre las 72 submissions reales, no solo hipótesis:
  - `backend/agent/risk_node.py`: `_has_critical_flags()` marcaba como flag crítico cualquier `risk_flag` que mencionara palabras como "loss ratio" o "siniestros", sin distinguir "el dato es alarmante" de "el dato no está informado". Como cnae_code/loss_history/loss_ratio nunca se parsean de adjuntos (limitación conocida, ver DUDA-004), el LLM casi siempre generaba un flag del tipo "Loss ratio no informado", que disparaba el match en el 100% de las 72 submissions. Fix: excluir del match los flags que solo señalan ausencia de dato (patrones "no informad", "sin informar", etc.).
  - `backend/prompts/risk_node.md`: la regla de escalación automática a HITL-3 incluía "coberturas combinadas (property + casualty)", que es la combinación estándar de cualquier póliza comercial normal, no un factor de riesgo real. Disparaba en 33 de 49 casos sobre-escalados. Fix: acotar la regla a combinaciones de 3+ líneas sustancialmente distintas, y añadir instrucción explícita de que la ausencia de CNAE/loss_history/loss_ratio no debe subir el risk_score.
  - `backend/prompts/appetite_node.md`: la regla de veredicto escalaba a "revision" automáticamente cualquier actividad que no apareciera en los guidelines RAG (que tiene cobertura incompleta de actividades comunes: ascensores, academias, data centers). Fix: cambiar el criterio de "no está en la lista → revision" a "evalúa el riesgo real de la actividad; si es estándar sin factores agravantes, clasifica dentro aunque no esté listada explícitamente".
- **h) Cambio de modelo Azure OpenAI de gpt-5.4 a gpt4o**, factor decisivo para CA-07: con gpt-5.4 el LLM-Judge daba consistentemente 49-75/100 (por debajo del umbral 85) por alucinaciones en risk_summary/quote_draft; con gpt4o y el mismo prompt, 92-97/100.

**Resultado final verificado** (experimento LangSmith `chubb-uw-e2e-80b0e41d`, 72/72 sin errores, 50 min):

| CA | Baseline (gpt-5.4, sin fixes) | Final (gpt4o + 3 fixes) | Umbral | Estado |
|---|---|---|---|---|
| CA-01 LOB accuracy | 0% (bug de medición) | 91.7% | ≥95% | Cerca |
| CA-02 Extracción | 96.8% | 96.8% | ≥80% | Cumple |
| CA-03 Missing fields | 80.6% | 80.6% | ≥90% | No cumple |
| CA-04 Appetite | 86.1% | 91.7% | ≥85% | Cumple |
| CA-05 RAG citas | 100% | 100% | 100% | Cumple |
| CA-06 HITL routing | 43.1% | 69.4% | ≥95% | No cumple |
| CA-07 LLM-Judge | 0% (real) | 100% | ≥85 en ≥90% | Cumple |
| CA-08 Time-to-quote | 100% | 100% | <4min en ≥95% | Cumple |

**Causa raíz pendiente (no arreglada esta sesión, requiere desarrollo real):** HITL-1 (datos incompletos) nunca se activa (0/14 en ambas pasadas). No es un bug de prompt: es que `route_after_extraction` solo puede detectar como "faltante" lo que vendría del email, pero el ground truth espera que cnae_code/loss_history (que solo están en adjuntos) cuenten como faltantes. Como no existe pdf_parser todavía (ver DUDA-004 y catálogo de herramientas Fase 3+ en ARCHITECTURE.md), esos campos nunca se marcan como missing_fields de verdad. Arreglarlo requiere o (a) implementar pdf_parser real, o (b) decidir una regla de negocio explícita para cuándo la ausencia de estos campos concretos debe forzar HITL-1 sin tener el adjunto parseado. Esto es la siguiente fase de trabajo, no un ajuste de esta sesión.

> **CORRECCIÓN 2026-07-02 (sesión posterior, no borrar lo anterior):** El diagnóstico del párrafo de arriba era **incorrecto**. Al investigar HITL-1 en detalle se encontró que `missing_fields_expected` de las 14 submissions HITL-1 **nunca contiene cnae_code/loss_history/loss_ratio** — solo `requested_coverages` y/o `sum_insured_eur`, que son campos de **email** que Node 2 ya lee. La causa real era una **contaminación de datos sintéticos**: el `email_raw.body` seguía conteniendo el valor de esos campos aunque el ground truth los marcaba como faltantes (ver **DUDA-005**). Implementar `pdf_parser` NO habría arreglado HITL-1 (incluso lo habría empeorado, al rellenar más campos desde el adjunto). Corregido editando el email de las 14 submissions para hacerlo consistente con el ground truth. `pdf_parser` queda **descartado como solución a HITL-1**; sigue siendo una mejora legítima pendiente para CA-02 si se decide abordar como iniciativa aparte.

**Nota de seguridad:** durante esta sesión se compartieron en texto plano, dentro de una conversación de chat, la `AZURE_OPENAI_API_KEY` y dos `LANGSMITH_API_KEY` (una ya inválida). Pendiente rotación por precaución.
> **Actualización 2026-07-04:** RESUELTO — claves rotadas.

---

## Sesión 2026-06-30 — Fase 0: Setup repositorio

**Objetivo:** Crear la estructura completa del repositorio y verificar conexión LangSmith.

**Trabajo realizado:**
- Creada estructura completa de carpetas según estándar acordado
- Creados todos los archivos raíz: CLAUDE.md, README.md, .env.example, .gitignore, requirements.txt
- Creados archivos de contexto: ARCHITECTURE.md, PROJECT_CONTEXT.md, DEVELOPMENT_PLAN.md, SESSION_LOG.md, DUDAS.md
- Creado observability/langsmith/setup_langsmith.py
- Creado evals/README.md con los 8 criterios de aceptación (CA-01 a CA-08)

**Decisiones tomadas:**
- Stack confirmado: Python 3.11+, LangGraph, LangSmith, ChromaDB local, Anthropic claude-sonnet-4-6
- DUDA-001 resuelta por defecto: Anthropic directa (pendiente confirmación Chubb)
- DUDA-002 resuelta por defecto: ChromaDB local para PoC

**Próxima sesión:** Fase 1 — Generación de datos sintéticos

---

## Sesión 2026-06-30 — Fase 1 completada + inicio Fase 2

**Objetivo:** Validar datos sintéticos y arrancar andamiaje del grafo.

**Datos sintéticos validados (Fase 1 cerrada):**
- 72 submissions: 36 Property + 36 Casualty (incluidos 12 edge cases)
- Distribución HITL: STP×27, HITL-1×14, HITL-2×10, HITL-3×21
- Campos ground-truth completos: 14 campos por submission
- 9 campos en extracted_data_ground_truth: activity_description, cnae_code, company_name, loss_history, loss_ratio, province, renewal, requested_coverages, sum_insured_eur
- Documentos RAG: appetite_guidelines (11KB) + pricing_guidelines (7.8KB) en backend/kb/raw/ y data/base/

**Decisiones:**
- DUDA-003 resuelta: pricing tool = stub simulado (sin API interna Chubb)
- LangSmith TRACING_V2=false temporalmente (key con 403, pendiente resolución)
- LLM confirmado: Azure OpenAI gpt-4.1 (langchain-openai)

**Fase 3E completada en la misma sesión:**
- backend/prompts/output_node.md — generación de 3 outputs con estado completo
- backend/prompts/reflection_node.md — rúbrica 5 dimensiones × 20 pts (umbral 85/100)
- backend/agent/output_node.py — generación + reflexión + regeneración (max 1 ciclo)
- CA-07: 3/3 outputs aprobados, score 100/100 en los 3 escenarios ✓
- CA-08: time-to-quote 21-25s en modo STP (muy por debajo de 4 min) ✓
- Reflection: todos aprobados en primera reflexión, sin regeneración necesaria
- Tokens output+reflection: ~2.900-3.060 por submission
- Outputs cubren 3 escenarios: STP (indicación favorable), HITL-3 (en análisis), HITL-2 (fuera apetito)

**Fase 3D completada en la misma sesión:**
- backend/prompts/risk_node.md + backend/agent/risk_node.py — LLM scoring + RAG pricing
- pricing stub v2: tasas reales de guidelines via RAG (tasa_min/max + risk_factor 0.85-1.25)
- 5 criterios automáticos de HITL-3: SA>6M, loss_ratio>0.45, revisión+agravantes, >2 siniestros, coberturas combinadas
- CA-06: 4/4 HITL correctos (100%) ✓
- Risk scores: estándar=38, químicos=92, pirotecnia=100, data center=95 — todos coherentes
- Primas: academia 3.080 EUR, químicos 15.077 EUR, pirotecnia 34.201 EUR (con tasas RAG)
- Fix: fallback a tasas por defecto cuando RAG no encuentra CNAE exacto

**Fase 3C completada en la misma sesión:**
- scripts/index_kb.py — chunking por sección ### + ChromaDB (all-MiniLM-L6-v2, 26 chunks, cosine)
- backend/tools/rag_retriever.py — retrieve() + format_context()
- backend/prompts/appetite_node.md + backend/agent/appetite_node.py — RAG + LLM + routing
- CA-04: 3/4 correctos (75%) — fallo en SUB-002 clínica dental: guidelines ambiguos entre dentro/revision
- CA-05: 4/4 con citas RAG (100%) ✓
- HITL-2 activa correctamente en casos fuera y revision ✓
- Tokens appetite: ~1.700-1.960 por submission
- Nota: SUB-002 es caso límite — guidelines dicen "evaluar con RC" → LLM elige revision, GT dice dentro

**Fase 3A completada en la misma sesión:**
- backend/utils/llm.py — AzureChatOpenAI inicializado desde .env
- backend/prompts/plan_node.md + intake_node.md
- plan_node.py — LLM genera plan de 5 pasos con anticipación por submission (920 tokens SUB-002)
- intake_node.py — LLM clasifica LOB, extrae broker/tomador/renovación con confianza
- Decisión técnica: replace() en lugar de str.format() para prompts con bloques JSON
- CA-01 verificado: LOB correcta en SUB-002 (property ✓, confianza high)
- Coste aproximado por submission en Fase 3A: ~1.546 tokens (plan+intake)

**Fase 2 completada en la misma sesión:**
- AgentState TypedDict con 17 campos en backend/agent/state.py
- 6 nodos stub: plan_node, intake_node, extraction_node, appetite_node, risk_node, output_node
- 3 aristas condicionales con funciones de routing
- Grafo compilado con interrupt_before en hitl_point_1/2/3
- Checkpointer SQLite (langgraph-checkpoint-sqlite 3.1.0) en checkpoints.db
- Pricing stub con firma realista (suma_asegurada × tasa_base × risk_factor)
- Smoke test STP: 6 nodos ejecutados, prima 11.312 EUR, OK
- Smoke test HITL-1: pausa en hitl_point_1, reanudación tras aprobación UW, OK

---
