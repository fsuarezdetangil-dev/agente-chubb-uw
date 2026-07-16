# agente-chubb-uw

PoC del P&C Underwriting Agent para **Chubb EMEA** (hub Madrid). Automatiza el ciclo de suscripción de Commercial Lines — Property y Casualty, riesgos estándar — usando un agente LangGraph con seis nodos secuenciales, RAG sobre guidelines de apetito y tres puntos de revisión humana (HITL).

## Prerequisitos

- Python 3.11+
- Azure OpenAI (deployment configurado en `.env` como `AZURE_OPENAI_DEPLOYMENT`)
- API key de [Arize Phoenix](https://app.phoenix.arize.com/) para observabilidad y experimentos

## Arranque en local

```bash
cp .env.example .env          # rellenar las variables en .env
pip install -r requirements.txt
python observability/phoenix/init_tracing.py
```

## Arquitectura del grafo

El agente es un grafo LangGraph compilado en `backend/agent/graph.py`. El flujo principal es lineal; las aristas condicionales desvían a puntos HITL cuando se cumplen las condiciones de activación.

```
START
  │
  ▼
┌──────────────────┐
│  Plan JSON Node  │  genera el plan de ejecución antes de actuar
└──────────────────┘
  │
  ▼
┌──────────────────┐
│ Submission Intake│  clasifica LOB, canal y extrae metadata del broker
└──────────────────┘
  │
  ▼
┌──────────────────┐
│ Data Extraction  │  extrae campos estructurados del email y adjuntos
└──────────────────┘
  │
  ├──[missing_fields > umbral]──► HITL Punto 1
  │
  ▼
┌──────────────────────┐
│ Appetite & Validation│  RAG sobre guidelines + veredicto (dentro/decline/refer)
└──────────────────────┘
  │
  ├──[verdict == decline | refer]──► HITL Punto 2
  │
  ▼
┌──────────────────┐
│ Risk Assessment  │  risk_score 0-100, red flags, pricing stub
└──────────────────┘
  │
  ├──[risk_score > 75 | flags críticos]──► HITL Punto 3
  │
  ▼
┌──────────────────┐
│ Output Generation│  risk_summary + quote_draft + broker_comm con reflexión
└──────────────────┘
  │
  ▼
END
```

## Nodos

| Nodo | Archivo | Responsabilidad |
|---|---|---|
| Plan JSON Node | `backend/agent/plan_node.py` | Plan de ejecución (lista de pasos) antes de actuar |
| Submission Intake | `backend/agent/intake_node.py` | LOB, canal, metadata del broker |
| Data Extraction | `backend/agent/extraction_node.py` | Campos estructurados de email y adjuntos |
| Appetite & Validation | `backend/agent/appetite_node.py` | RAG sobre guidelines + veredicto de apetito |
| Risk Assessment | `backend/agent/risk_node.py` | Puntuación de riesgo, red flags, pricing |
| Output Generation | `backend/agent/output_node.py` | Tres outputs finales + reflexión de calidad |

Los prompts de cada nodo están en `backend/prompts/<nodo>.md`, versionados en el repo.

## AgentState

Definido en `backend/agent/state.py` como `TypedDict`. Todos los nodos leen y escriben sobre este estado compartido.

```python
class AgentState(TypedDict):
    # Entrada
    submission_id: str
    submission_raw: dict       # email + attachments originales
    channel: str               # email | portal | api
    line_of_business: str      # property | casualty
    metadata: dict             # broker, tomador, fecha
    # Extracción
    extracted_data: dict
    missing_fields: list[str]
    missing_fields_at_extraction: list[str]
    # Apetito
    appetite_result: dict      # veredicto + justificación + citas RAG
    # Riesgo
    risk_score: int            # 0-100
    risk_flags: list[str]
    pricing_output: dict
    # Output
    outputs: dict              # risk_summary, quote_draft, broker_comm
    # Control de flujo
    audit_log: list[dict]
    hitl_status: str           # pending | approved | rejected | none
    hitl_point: str            # point_1 | point_2 | point_3 | none
    plan_json: list[dict]
```

## HITL

Los tres puntos de revisión humana están implementados con `interrupt_before` de LangGraph. El estado se persiste en SQLite checkpointer (`checkpoints.db`).

| Punto | Se activa cuando | Acción del UW |
|---|---|---|
| HITL-1 | `missing_fields` supera umbral | Completar campos / rechazar |
| HITL-2 | `appetite_result.verdict` es `decline` o `refer` | Override del veredicto de apetito |
| HITL-3 | `risk_score > 75` o flags críticos presentes | Aprobar / ajustar condiciones / declinar |

## Evaluación (Arize Phoenix)

El agente se evalúa sobre un golden dataset de 72 submissions (`chubb-uw-golden-72`) con ocho criterios de aceptación.

| Métrica | Umbral | Baseline v1 | Estado |
|---|---|---|---|
| CA-01 LOB accuracy | ≥ 95% | ~89% | Pendiente (fixes en prompts) |
| CA-02 Extraction | ≥ 80% campos críticos | ~99% | Cumple |
| CA-03 Missing fields | ≥ 90% | ~100% | Cumple |
| CA-04 Appetite | ≥ 85% | ~92% | Cumple |
| CA-05 RAG citas | 100% | ~100% | Cumple |
| CA-06 HITL routing | ≥ 95% | ~72% | Pendiente (fixes en prompts) |
| CA-07 LLM-Judge | ≥ 85 pts en ≥ 90% | ~100% | Cumple |
| CA-08 Time-to-quote | < 4 min en ≥ 95% | ~100% | Cumple |

Experimentos publicados en `observability/phoenix/exports/`:
- `e2e-v1-baseline-traced.csv` — baseline (68/72 runs)
- `e2e-v2-prompt-fixes.csv` — tras aplicar fixes en prompts de CA-01 y CA-06

Scripts de evaluación: `scripts/run_phoenix_eval.py`, `scripts/upload_phoenix_dataset.py`.

## Estructura del repositorio

```
backend/
  agent/          # grafo, nodos, estado
  prompts/        # prompts por nodo en markdown (versionados)
  kb/             # base de conocimiento RAG (raw + processed + index)
context/          # ARCHITECTURE.md, DEVELOPMENT_PLAN.md, PROJECT_CONTEXT.md
data/             # dataset sintético de 72 submissions
evals/            # evaluadores CA-01..CA-08
observability/    # tracing Phoenix + exports de experimentos
scripts/          # harness de evaluación y carga de datasets
```

## Documentación

- Arquitectura detallada: [context/ARCHITECTURE.md](context/ARCHITECTURE.md)
- Contexto del proyecto y criterios de éxito: [context/PROJECT_CONTEXT.md](context/PROJECT_CONTEXT.md)
- Plan de desarrollo por fases: [context/DEVELOPMENT_PLAN.md](context/DEVELOPMENT_PLAN.md)
- Criterios de aceptación: [evals/README.md](evals/README.md)
