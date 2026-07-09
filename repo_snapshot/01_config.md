# 01 — Configuración del proyecto

No existe `pyproject.toml`, `setup.py`, `setup.cfg` ni `Pipfile`. La única gestión de
dependencias es `requirements.txt`.

---

## `requirements.txt` (204 bytes, 10 líneas)

```txt
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.3.0
langchain-community>=0.3.0
langsmith>=0.1.0
chromadb>=0.5.0
openai>=1.0.0
langgraph-checkpoint-sqlite>=2.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
```

> ⚠️ Nota: figura `langchain-openai` (Azure OpenAI). **NO** hay `langchain-anthropic`,
> pese a que CLAUDE.md y README.md dicen que el modelo es `claude-sonnet-4-6`. Ver `08_llm_provider_check.md`.

---

## `.env.example` (550 bytes, 13 líneas)

```dotenv
# Azure OpenAI
AZURE_OPENAI_API_KEY=           # API key de Azure OpenAI
AZURE_OPENAI_ENDPOINT=          # https://<tu-recurso>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=        # nombre del deployment (ej. gpt-4.1)
AZURE_OPENAI_API_VERSION=       # ej. 2025-01-01-preview
# LangSmith
LANGSMITH_API_KEY=              # API key de LangSmith (https://smith.langchain.com/settings)
LANGCHAIN_TRACING_V2=true       # activa el tracing automático
LANGCHAIN_PROJECT=agente-chubb-uw  # nombre del proyecto en LangSmith
# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## `.env` (real) — ⚠️ EXISTE, CON VALORES REALES — NO REPRODUCIDO

Confirmado: existe un `.env` real en la raíz (442 bytes). **Contiene secretos reales**
(entre ellos una `LANGSMITH_API_KEY` con valor `lsv2_pt_...` y las variables de Azure
OpenAI). Por seguridad **no se copia su contenido aquí**.

Estructura de claves presentes en el `.env` real (solo nombres, sin valores):
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION` = `2025-01-01-preview`
- `LANGSMITH_API_KEY`  (valor real presente)
- `LANGCHAIN_TRACING_V2` = `true`
- `LANGCHAIN_PROJECT` = `agente-chubb-uw`
- `API_HOST`, `API_PORT`

> 🔴 Riesgo de seguridad detectado: el `.env` con la key real está en el filesystem.
> Está correctamente ignorado por `.gitignore`, pero conviene rotar la key de LangSmith
> si este directorio se ha compartido o sincronizado (OneDrive).

---

## `.gitignore` (91 bytes, 9 líneas)

```gitignore
.env
__pycache__/
*.pyc
.DS_Store
data/samples/*.json
backend/kb/index/
*.db
node_modules/
```

> Observación: `data/samples/*.json` y `backend/kb/index/` están ignorados. Es decir,
> el golden dataset y el índice ChromaDB **no se versionarían** en git. Pero el repo NO es
> un repositorio git actualmente (no hay `.git`).

---

## `CLAUDE.md` (1279 bytes, 36 líneas)

```markdown
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
​```bash
pip install -r requirements.txt
python observability/langsmith/setup_langsmith.py
python backend/agent/graph.py   # cuando exista (Fase 2+)
​```

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
```

> ⚠️ Contradicción clave: CLAUDE.md afirma **"Anthropic API — modelo `claude-sonnet-4-6`"**,
> pero el código real usa Azure OpenAI (ver `08_llm_provider_check.md`).
