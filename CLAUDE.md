# agente-chubb-uw

## Qué es este proyecto
PoC del P&C Underwriting Agent para Chubb EMEA. Agente LangGraph combinado agéntico + RAG. Cinco nodos secuenciales con tres puntos HITL (Human-in-the-Loop) obligatorios. Automatiza el ciclo de suscripción de Commercial Lines (Property y Casualty, riesgos estándar).

## Stack
- Python 3.11+
- LangGraph (orquestación del agente)
- LangChain (integración de herramientas y LLM)
- Arize Phoenix (observabilidad y trazabilidad — reemplazó a LangSmith)
- LangSmith (solo harness de evaluación — `evals/evaluators.py`)
- ChromaDB (vector store local para PoC)
- Azure OpenAI — deployment `gpt4o` (configurado en `.env`)

## Comandos de arranque
```bash
pip install -r requirements.txt
python scripts/run_e2e.py            # pasada completa 72 submissions
python scripts/run_phoenix_eval.py   # experimento con métricas en Phoenix
python backend/agent/graph.py        # smoke test del grafo
```

## Convenciones
- Comentarios en **español**
- Nombres de variables y funciones en **inglés**
- Un archivo por nodo en `backend/agent/`
- Un prompt `.md` por nodo en `backend/prompts/`

## Al arrancar una sesión nueva
1. Leer este archivo (CLAUDE.md)
2. Leer `context/ARCHITECTURE.md`
3. Leer `context/SESSION_LOG.md`

## Restricciones
- No usar datos reales de asegurados
- No commitear `.env` con valores reales
- No crear carpetas nuevas en la raíz sin aprobación previa
- No añadir dependencias a `requirements.txt` sin justificarlo
