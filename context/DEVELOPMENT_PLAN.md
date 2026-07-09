# DEVELOPMENT_PLAN — agente-chubb-uw

## Fases del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| **Fase 0** | Setup repositorio | **EN CURSO** |
| **Fase 1** | Datos sintéticos (72 submissions Property + Casualty + edge cases) | **COMPLETADA 2026-06-30** |
| **Fase 2** | Andamiaje del grafo (AgentState + nodos stub + checkpointer) | **COMPLETADA 2026-06-30** |
| **Fase 3A** | Node 1 Submission Intake + Plan JSON Node | **COMPLETADA 2026-06-30** |
| **Fase 3B** | Node 2 Data Extraction (field_extractor LLM, sin pdf_parser) | **COMPLETADA 2026-06-30** |
| **Fase 3C** | Node 3 Appetite & Validation + RAG + HITL Punto 1 | **COMPLETADA 2026-06-30** |
| **Fase 3D** | Node 4 Risk Assessment + HITL-2 y HITL-3 + pricing stub v2 RAG | **COMPLETADA 2026-06-30** |
| **Fase 3E** | Node 5 Output Generation + Reflection pattern | **COMPLETADA 2026-06-30** |
| **Fase E2E** | Pasada completa 72 submissions — métricas CA-01 a CA-08 | **COMPLETADA 2026-07-04 — 6/8 CA cumplen umbral (ver SESSION_LOG.md, experimento chubb-uw-e2e-d1881dca)** |
| Fase 4 | Golden dataset + evals + LangSmith evaluators | **COMPLETADA 2026-07-04 — LangSmith conectado (cuenta Nicolás, proyecto agente-chubb-uw-nicolas, endpoint EU), dataset chubb-uw-golden-72 subido. Experimentos publicados: chubb-uw-e2e-80b0e41d (2026-07-02), chubb-uw-e2e-d7973ef5 (2026-07-02), chubb-uw-e2e-d1881dca (2026-07-04, pasada final)** |
| Fase 5 | Demo preparación + presentación Chubb EMEA | PENDIENTE |
| Fase 6 | ~~Implementar pdf_parser real para cerrar HITL-1 (CA-03/CA-06)~~ | **CORREGIDO 2026-07-02** |
| Fase 7 | Investigar causa raíz de CA-01 (LOB, 7 fallos de 72) y CA-06 (HITL routing, 7 fallos en STP/HITL-3) | PENDIENTE |
| **Fase 8** | Parseo real de adjuntos (CA-02) + bandeja de HITL pendientes (backend + CLI) | **COMPLETADA 2026-07-08 — validación local; pendiente pasada agregada en LangSmith (ver SESSION_LOG.md y DUDA-007)** |

> **Corrección Fase 6 (2026-07-02):** El diagnóstico original ("falta pdf_parser") era **incorrecto**. La causa real de que HITL-1 no se activara era una contaminación de datos sintéticos entre `email_raw` y `missing_fields_expected` en las 14 submissions HITL-1 (ver **DUDA-005** y corrección en SESSION_LOG.md 2026-07-02). Se corrigió editando el email para hacerlo consistente con el ground truth ya existente, **sin** implementar pdf_parser. `pdf_parser` queda descartado como solución a HITL-1; sigue siendo una mejora legítima pendiente para **CA-02** (parsear cnae_code/loss_history/loss_ratio de adjuntos) si se decide abordar como iniciativa separada.

> **Actualización Fase 8 (2026-07-08):** La mejora de CA-02 vía adjuntos (anticipada arriba) se materializó en la Fase 8, **sin pdf_parser**: los adjuntos del dataset ya son texto extraído (`extracted_text_summary`), no PDFs reales, así que bastó con leer ese campo (había un bug que leía la clave equivocada) y ajustar el prompt. `cnae_code`/`loss_history`/`loss_ratio` ahora se extraen del adjunto. Al encender el parseo apareció una contaminación paralela en los adjuntos (ver **DUDA-007**), corregida para no romper el fix de HITL-1. `pdf_parser` real seguiría siendo necesario solo cuando Chubb aporte documentos reales en producción (quedaría como stub con firma equivalente, igual que `pricing_tool`).

---

## Detalle Fase 0 — COMPLETADA 2026-06-30

- [x] Crear estructura de carpetas del repositorio
- [x] Crear archivos raíz: CLAUDE.md, README.md, .env.example, .gitignore, requirements.txt
- [x] Crear archivos de contexto: ARCHITECTURE.md, PROJECT_CONTEXT.md, DEVELOPMENT_PLAN.md, SESSION_LOG.md, DUDAS.md
- [x] Crear observability/langsmith/setup_langsmith.py
- [x] Crear evals/README.md con criterios de aceptación
- [ ] Instalar requirements.txt sin errores
- [ ] Ejecutar setup_langsmith.py y verificar conexión

---

## Detalle Fase 1 — PENDIENTE

- [x] 72 submissions generadas (36 Property + 36 Casualty, incluidos 12 edge cases)
- [x] Campos ground-truth: submission_id, line_of_business, scenario_tag, channel, broker, received_at, email_raw, attachments, extracted_data_ground_truth, missing_fields_expected, appetite_expected, complete_data_expected, expected_hitl_trigger, expected_hitl_trigger_reason
- [x] Documentos RAG: appetite_guidelines y pricing_guidelines en data/base/ y backend/kb/raw/
- [x] Cobertura de escenarios: STP×27, HITL-1×14, HITL-2×10, HITL-3×21
- [ ] Crear `data/base/schemas.py` con Pydantic models (se hace en Fase 2)

---

## Detalle Fase 4 — PARCIAL 2026-06-30

### Objetivo
Evaluación formal del agente con LangSmith Experiments, trazabilidad por submission, y comparación de experimentos.

### Completado
- [x] `evals/evaluators.py` — 8 evaluadores (CA-01 a CA-08) con doble firma: standalone + LangSmith
- [x] `scripts/upload_dataset.py` — sube el golden dataset de 72 submissions a LangSmith
- [x] `scripts/run_langsmith_eval.py` — harness `langsmith.evaluate()` con `max_concurrency=1`

### Pendiente (bloqueado por LangSmith key 403)
- [x] Obtener LANGCHAIN_API_KEY válida en smith.langchain.com
- [x] Ejecutar `upload_dataset.py` para crear dataset "chubb-uw-golden-72"
- [x] Ejecutar `run_langsmith_eval.py` y publicar primer Experiment
- [ ] Añadir `config={"metadata": {"submission_id": ...}}` a las llamadas LLM para trazar tokens por submission
- [ ] Crear dashboard con agregación de métricas CA-01 a CA-08

### Umbral de aceptación
| Métrica | Umbral | Prioridad |
|---|---|---|
| CA-01 LOB accuracy | ≥ 95% | Must |
| CA-02 Extraction | ≥ 80% campos críticos | Should |
| CA-03 Missing fields | ≥ 90% | Must |
| CA-04 Appetite | ≥ 85% | Must |
| CA-05 RAG citas | 100% | Must |
| CA-06 HITL routing | ≥ 95% | Must |
| CA-07 LLM-Judge | ≥ 85 pts en ≥ 90% | Should |
| CA-08 Time-to-quote | < 4 min en ≥ 95% | Must |

### Estado actual vs umbral (experimento chubb-uw-e2e-d1881dca, 2026-07-04)

| Métrica | Umbral | Resultado | Estado |
|---|---|---|---|
| CA-01 LOB accuracy | ≥ 95% | 90.3% (65/72) | Pendiente |
| CA-02 Extraction | ≥ 80% | 99.1% (68/72) | Cumple ✓ |
| CA-03 Missing fields | ≥ 90% | 100% (72/72) | Cumple ✓ |
| CA-04 Appetite | ≥ 85% | 91.7% (66/72) | Cumple ✓ |
| CA-05 RAG citas | 100% | 100% (72/72) | Cumple ✓ |
| CA-06 HITL routing | ≥ 95% | 90.3% (65/72) | Pendiente |
| CA-07 LLM-Judge | ≥ 85 pts en ≥ 90% | 100% (72/72) | Cumple ✓ |
| CA-08 Time-to-quote | < 4 min en ≥ 95% | 100% (72/72) | Cumple ✓ |

---

## Notas de arquitectura

Ver diseño completo en [ARCHITECTURE.md](ARCHITECTURE.md).
Dudas pendientes de resolución en [DUDAS.md](DUDAS.md).

**Modelo LLM en uso (2026-07-02):** `gpt4o` de **Azure OpenAI** (deployment configurado en `.env` como `AZURE_OPENAI_DEPLOYMENT`), **no** `claude-sonnet-4-6` como indicaban originalmente CLAUDE.md y DUDA-001. Esta discrepancia en CLAUDE.md/DUDAS.md **sigue sin corregirse formalmente** — habría que actualizar ambos documentos en una pasada de limpieza de documentación.
