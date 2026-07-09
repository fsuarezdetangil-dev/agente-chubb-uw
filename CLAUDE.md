# agente-chubb-uw

## Qué es este proyecto
PoC del P&C Underwriting Agent para Chubb EMEA. Agente LangGraph combinado agéntico + RAG. Cinco nodos secuenciales con tres puntos HITL (Human-in-the-Loop) obligatorios. Automatiza el ciclo de suscripción de Commercial Lines (Property y Casualty, riesgos estándar).

## Stack
- Python 3.11+
- LangGraph (orquestación del agente)
- LangChain (integración de herramientas y LLM)
- LangSmith (observabilidad y evaluación)
- ChromaDB (vector store local para PoC)
- Anthropic API — modelo `claude-sonnet-4-6`

## Comandos de arranque
```bash
pip install -r requirements.txt
python observability/langsmith/setup_langsmith.py
python backend/agent/graph.py   # cuando exista (Fase 2+)
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
