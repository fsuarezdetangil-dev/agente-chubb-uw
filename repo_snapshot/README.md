# Snapshot del repo `agente-chubb-uw` — Resumen

Generado el 2026-07-01. Solo lectura: **no se modificó ningún archivo del proyecto**.
Objetivo: dar a otra instancia de Claude el contexto completo para ayudar a completar la PoC.

## Índice de archivos del snapshot
- `00_tree.txt` — árbol completo con tamaños; marca carpetas vacías.
- `01_config.md` — requirements, .env.example, .gitignore, CLAUDE.md (`.env` real: solo confirmado, no copiado).
- `02_agent_core.md` — state.py, graph.py y los 6 nodos + utils/llm.py, íntegros.
- `03_prompts.md` — los 7 prompts `.md`.
- `04_tools_and_rag.md` — rag_retriever.py, index_kb.py y estructura de kb/.
- `05_observability.md` — setup_langsmith.py + grep de LangSmith (key real enmascarada).
- `06_evals.md` — evaluators.py, upload_dataset.py, run_langsmith_eval.py, evals/README.md.
- `07_data_sample.md` — 1 submission completa + estructura de data/ + schemas.py.
- `08_llm_provider_check.md` — **resuelve la contradicción del proveedor LLM.**
- `09_test_status.md` — git, tests y resultados de la última pasada E2E.

## Qué se encontró (10–15 líneas)

1. **Todos los nodos están implementados de verdad**, no son stubs. `plan`, `intake`,
   `extraction`, `appetite`, `risk`, `output` llaman al LLM real. Los únicos "vacíos" son los
   3 nodos HITL (`lambda s: s`, a propósito, con `interrupt_before`) y el motor de pricing, que
   es un stub deliberado dentro de `risk_node.py` (`_call_pricing_stub`, tasas vía RAG).
2. **Proveedor LLM = Azure OpenAI (`gpt-4.1`), NO Anthropic.** `backend/utils/llm.py` usa
   `AzureChatOpenAI`; no hay rastro de `langchain_anthropic`/`ChatAnthropic`. Esto **contradice**
   CLAUDE.md, README.md y DUDA-001, que aún dicen `claude-sonnet-4-6`. SESSION_LOG sí confirma
   Azure. → Hay que corregir la documentación de cabecera.
3. **LangSmith está cableado pero nunca funcionó.** Evaluadores CA-01..08 con doble firma
   (local + LangSmith), scripts `upload_dataset.py` y `run_langsmith_eval.py` listos, y tracing
   por env vars. Pero la key daba **403**, así que no hay dataset ni Experiments publicados. Toda
   la evaluación real se hizo con un runner local (`scripts/run_e2e.py`).
4. **La última pasada E2E quedó a medias: 55/72 OK.** Las 17 restantes (incl. TODOS los edge
   cases) fallaron por `Connection error` y un `403 - Virtual Network` de Azure (infraestructura,
   no código). Las métricas publicadas son solo sobre 55.
5. **Resultados: CA-06 HITL routing = 73%** (debería ser ≥95%; es el criterio más crítico) y
   **CA-03 missing fields = 80%** (target ≥90%) son los dos que fallan. CA-01/04/05/07/08 pasan;
   CA-07 sale 98/100 pero es autoevaluación con el mismo modelo (sesgo probable).

## Inconsistencias y cosas raras a vigilar
- **No es un repo git** (no hay `.git`) pese a que CLAUDE.md habla de "commitear". Vive en OneDrive.
- **`.env` real con `LANGSMITH_API_KEY` real** en el filesystem (enmascarada en el snapshot).
  Riesgo de fuga si la carpeta se comparte; conviene rotarla.
- **`data/base/schemas.py` está desalineado** con los datos reales en 3 campos (`broker`,
  `email_raw`, `loss_history`) y no se usa en el pipeline.
- **`evals/README.md` apunta a `evals/golden_dataset/` (vacía)**; el dataset real está en
  `data/samples/`. Y menciona "RAGAS Faithfulness" para CA-05, pero el evaluador solo cuenta
  citas (≥1), no calcula faithfulness.
- **Targets contradictorios** entre `evals/README.md` (CA-01 >90, CA-02 >92) y
  `evaluators.py`/`DEVELOPMENT_PLAN.md` (CA-01 ≥95, CA-02 ≥80).
- **Contrato roto entre scripts LangSmith:** `upload_dataset.py` mete la referencia en
  `Example.outputs`, pero `run_langsmith_eval.py` la busca en `inputs["__reference"]`.
- **"72 vs 70":** el archivo principal es `submissions_synthetic_all_70.json`; el total llega a
  72 al deduplicar con los 12 edge cases.
- **Embeddings locales** (all-MiniLM-L6-v2), no `text-embedding-3-small` como dice ARCHITECTURE.md.
- **`checkpoints.db` = 185 MB** (checkpointer acumulado); candidato a purga.
- Carpetas de andamiaje vacías: `backend/api/`, `backend/kb/processed/`, `observability/dashboards/`,
  `observability/span_analysis/`, `tests/*`, `evals/scripts/`, `evals/golden_dataset/`,
  `context/artifacts/`.

## Prioridades sugeridas para completar
1. Desbloquear Azure (VNet/endpoint) y relanzar el E2E completo sobre las 72 (faltan los edge cases).
2. Arreglar CA-06 (routing HITL) — 73% es inaceptable para el criterio "nunca saltar un HITL".
3. Conseguir key LangSmith válida y alinear el contrato de referencia entre los dos scripts.
4. Corregir docs de proveedor LLM (Azure) y arreglar `schemas.py`.
