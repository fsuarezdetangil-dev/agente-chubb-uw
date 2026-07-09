# 08 — Verificación crítica del proveedor LLM

## VEREDICTO: el código usa **Azure OpenAI**, NO Anthropic.

La contradicción entre documentos se resuelve así:
- **CLAUDE.md** y **README.md** dicen "Anthropic API — modelo `claude-sonnet-4-6`". → **Obsoleto/aspiracional.**
- **DUDAS.md (DUDA-001)** dice "por defecto Anthropic directa, pendiente confirmación". → **Superado por los hechos.**
- **SESSION_LOG.md (Fase 1 / Fase 3A)** dice "LLM confirmado: Azure OpenAI gpt-4.1 (langchain-openai)". → **Esto es lo que refleja el código.**

**El código en ejecución usa `AzureChatOpenAI` de `langchain_openai`.** No existe ninguna
importación de `langchain_anthropic` ni `ChatAnthropic` en todo el repo. `requirements.txt`
incluye `langchain-openai` y `openai`, pero **no** `langchain-anthropic`.

Modelo real = el deployment de Azure configurado en `.env` (`AZURE_OPENAI_DEPLOYMENT`, que
según `.env.example` y SESSION_LOG es `gpt-4.1`), con `AZURE_OPENAI_API_VERSION=2025-01-01-preview`.

---

## `grep -rn` en `backend/` — todos los resultados con contexto

Comando: `grep -rn -B2 -A2 -E "AzureChatOpenAI|ChatAnthropic|langchain_openai|langchain_anthropic|AZURE_OPENAI|ANTHROPIC_API_KEY" backend/`

```
backend/utils/llm.py-1-"""
backend/utils/llm.py-2-Inicialización del LLM compartido para todos los nodos.
backend/utils/llm.py:3:Usa AzureChatOpenAI con las variables de .env.
backend/utils/llm.py-4-"""
backend/utils/llm.py-5-
backend/utils/llm.py-6-import os
backend/utils/llm.py-7-from dotenv import load_dotenv
backend/utils/llm.py:8:from langchain_openai import AzureChatOpenAI
backend/utils/llm.py-9-
backend/utils/llm.py-10-load_dotenv()
backend/utils/llm.py-11-
backend/utils/llm.py-12-
backend/utils/llm.py:13:def get_llm(temperature: float = 0.0) -> AzureChatOpenAI:
backend/utils/llm.py:14:    """Devuelve una instancia de AzureChatOpenAI lista para usar."""
backend/utils/llm.py:15:    return AzureChatOpenAI(
backend/utils/llm.py:16:        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
backend/utils/llm.py:17:        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
backend/utils/llm.py:18:        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
backend/utils/llm.py:19:        api_key=os.environ["AZURE_OPENAI_API_KEY"],
backend/utils/llm.py-20-        temperature=temperature,
backend/utils/llm.py-21-    )
Binary file backend/utils/__pycache__/llm.cpython-314.pyc matches
```

- **Única definición del LLM:** `backend/utils/llm.py::get_llm()`.
- **Consumidores:** los 6 nodos (`plan`, `intake`, `extraction`, `appetite`, `risk`, `output`)
  importan `from ..utils.llm import get_llm` y llaman `get_llm(temperature=...)`. Ninguno
  instancia el modelo por su cuenta ni menciona Anthropic.
- **Cero coincidencias** de `ChatAnthropic`, `langchain_anthropic` o `ANTHROPIC_API_KEY` en
  `backend/` (ni en ninguna parte del repo).
- El bytecode `.pyc` en `__pycache__` confirma que `llm.py` ya se ha ejecutado con esta versión.

---

## Implicaciones para completar el proyecto

1. **La documentación de cabecera miente sobre el proveedor.** Antes de cualquier trabajo,
   corregir CLAUDE.md y README.md para que digan Azure OpenAI `gpt-4.1` (o dejar claro que
   Anthropic era solo el plan por defecto inicial y se descartó).
2. **DUDA-001 debe marcarse RESUELTA** → Azure OpenAI. Hoy figura como "pendiente".
3. **El endpoint de Azure tiene una VNet restringida.** El último E2E (2026-07-01) murió con
   `403 - A Virtual Network is configured for this resource`. El agente funciona, pero el
   acceso de red al recurso Azure es intermitente/restringido — probable causa raíz de los 17
   fallos "Connection error" de esa pasada. Esto es infraestructura, no código.
4. **`text-embedding-3-small` no se usa.** El RAG usa embeddings locales (all-MiniLM-L6-v2 de
   ChromaDB), no Azure ni OpenAI embeddings — pese a lo que dice ARCHITECTURE.md.
