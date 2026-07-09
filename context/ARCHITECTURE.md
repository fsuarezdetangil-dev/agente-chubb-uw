# ARCHITECTURE — agente-chubb-uw

Diseño acordado en sesión de diseño — Junio 2026.

---

## Diagrama del grafo

```
START
  │
  ▼
┌─────────────────────┐
│   Plan JSON Node    │  genera el plan de ejecución antes de actuar
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│  Submission Intake  │  clasifica línea de negocio, canal, broker
│     (Node 1)        │  herramientas: clasificador, extractor metadata
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│  Data Extraction    │  extrae campos estructurados de docs adjuntos
│     (Node 2)        │  herramientas: parser PDF, OCR, field extractor
└─────────────────────┘
  │
  ▼
  ├──[campos_faltantes > umbral]──► HITL Punto 1 (solicitar info al broker)
  │
  ▼
┌──────────────────────────┐
│  Appetite & Validation   │  consulta guidelines de apetito via RAG
│       (Node 3)           │  herramientas: RAG retriever, appetite checker
└──────────────────────────┘
  │
  ├──[fuera_de_apetito]──► HITL Punto 2 (revisión UW para declinar/referir)
  │
  ▼
┌─────────────────────┐
│  Risk Assessment    │  puntúa el riesgo, detecta red flags,
│     (Node 4)        │  invoca herramienta de pricing certificada
└─────────────────────┘
  │
  ├──[risk_score > 75 OR flags críticos]──► HITL Punto 3 (revisión UW senior)
  │
  ▼
┌─────────────────────┐
│ Output Generation   │  genera risk_summary, quote_draft, broker_comm
│     (Node 5)        │  con reflexión sobre calidad del output
└─────────────────────┘
  │
  ▼
END
```

---

## AgentState

```python
class AgentState(TypedDict):
    submission_id: str
    submission_raw: dict          # email + attachments originales
    channel: str                  # email | portal | api
    line_of_business: str         # property | casualty
    metadata: dict                # broker, tomador, fecha
    extracted_data: dict          # datos estructurados del riesgo
    missing_fields: list[str]     # campos faltantes detectados
    appetite_result: dict         # veredicto + justificación + citas
    risk_score: int               # 0-100
    risk_flags: list[str]         # red flags identificados
    pricing_output: dict          # prima técnica de herramienta certificada
    outputs: dict                 # risk_summary, quote_draft, broker_comm
    audit_log: list[dict]         # registro de cada paso ejecutado
    hitl_status: str              # pending | approved | rejected | none
    hitl_point: str               # point_1 | point_2 | point_3 | none
    plan_json: list[dict]         # Plan JSON generado antes de ejecutar
```

---

## Nodos del grafo

| Nodo | Archivo | Responsabilidad |
|---|---|---|
| Plan JSON Node | `backend/agent/plan_node.py` | Genera el plan de ejecución (lista de pasos) antes de que el agente actúe |
| Submission Intake | `backend/agent/intake_node.py` | Clasifica línea de negocio, canal de entrada y extrae metadata del broker |
| Data Extraction | `backend/agent/extraction_node.py` | Extrae campos estructurados desde PDFs, emails y formularios |
| Appetite & Validation | `backend/agent/appetite_node.py` | Consulta guidelines de apetito via RAG y produce veredicto |
| Risk Assessment | `backend/agent/risk_node.py` | Puntúa el riesgo, identifica flags y llama a la herramienta de pricing |
| Output Generation | `backend/agent/output_node.py` | Genera los tres outputs finales con reflexión sobre calidad |

---

## Aristas condicionales (routing)

| Condición | Origen | Destino |
|---|---|---|
| `missing_fields` supera umbral configurable | Data Extraction | HITL Punto 1 |
| `appetite_result.verdict == "decline"` o `"refer"` | Appetite & Validation | HITL Punto 2 |
| `risk_score > 75` o flags críticos presentes | Risk Assessment | HITL Punto 3 |

En todos los demás casos el flujo continúa al siguiente nodo sin interrupción (modo STP).

---

## Puntos HITL

Implementados con `interrupt_before` de LangGraph. El estado se persiste en SQLite checkpointer.

| Punto | Nodo que lo activa | Acción del UW |
|---|---|---|
| HITL Punto 1 | Data Extraction | Aprobar / completar campos faltantes / rechazar submission |
| HITL Punto 2 | Appetite & Validation | Aprobar derivación / override del veredicto de apetito |
| HITL Punto 3 | Risk Assessment | Aprobar pricing / ajustar condiciones / declinar |

---

## Catálogo de herramientas (Fase 3+)

| Herramienta | Descripción | Nodo que la usa |
|---|---|---|
| `pdf_parser` | Extrae texto y tablas de PDFs adjuntos | Data Extraction |
| `field_extractor` | Extrae campos estructurados via LLM con schema Pydantic | Data Extraction |
| `rag_retriever` | Recupera fragmentos relevantes de los guidelines de apetito | Appetite & Validation |
| `appetite_checker` | Aplica reglas de apetito sobre los datos extraídos | Appetite & Validation |
| `pricing_tool` | Herramienta certificada de cálculo de prima técnica (stub en PoC) | Risk Assessment |
| `risk_scorer` | Calcula risk_score 0-100 y detecta red flags | Risk Assessment |

---

## Estrategia RAG

- **Base de conocimiento:** guidelines de apetito de suscripción de Chubb EMEA (documentos PDF internos)
- **Chunking:** por sección, 512 tokens, overlap 50 tokens
- **Embedding model:** `text-embedding-3-small` de OpenAI o equivalente de Anthropic
- **Vector store:** ChromaDB local en `backend/kb/index/` (PoC) → Azure Cognitive Search en producción
- **Raw docs:** `backend/kb/raw/` — PDFs originales, no versionados
- **Processed docs:** `backend/kb/processed/` — chunks en JSON listos para indexar
- **Evaluación RAG:** RAGAS Faithfulness > 0.90 (CA-05)
