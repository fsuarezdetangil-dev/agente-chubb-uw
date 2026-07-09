# agente-chubb-uw

PoC del P&C Underwriting Agent para **Chubb EMEA** (hub Madrid). Automatiza el ciclo de suscripción de Commercial Lines — Property y Casualty, riesgos estándar — usando un agente LangGraph combinado agéntico + RAG con cinco nodos secuenciales y tres puntos de revisión humana (HITL).

## Prerequisitos
- Python 3.11+
- Cuenta y API key de [LangSmith](https://smith.langchain.com/)
- API key de [Anthropic](https://console.anthropic.com/) (modelo `claude-sonnet-4-6`)

## Arranque en local
```bash
cp .env.example .env          # rellenar las API keys en .env
pip install -r requirements.txt
python observability/langsmith/setup_langsmith.py
```

## Documentación
- Arquitectura del agente: [context/ARCHITECTURE.md](context/ARCHITECTURE.md)
- Contexto del proyecto y criterios de éxito: [context/PROJECT_CONTEXT.md](context/PROJECT_CONTEXT.md)
- Plan de desarrollo por fases: [context/DEVELOPMENT_PLAN.md](context/DEVELOPMENT_PLAN.md)
- Criterios de aceptación de evals: [evals/README.md](evals/README.md)
