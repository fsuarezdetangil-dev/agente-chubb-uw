# 05 — Observabilidad (LangSmith)

Estado real: el cableado de LangSmith existe pero **el tracing automático NO está activado
en el código del agente**. No hay callbacks explícitos ni `config={"metadata": ...}` en las
llamadas al LLM. El tracing depende únicamente de las variables de entorno
`LANGCHAIN_TRACING_V2=true` + `LANGSMITH_API_KEY`, que LangChain lee automáticamente. Según
SESSION_LOG y DEVELOPMENT_PLAN, la key dio **error 403** y el tracing se dejó desactivado
temporalmente. La última pasada E2E incluso terminó con un `403 - A Virtual Network is
configured for this resource` de Azure (no de LangSmith), lo que abortó 17 submissions.

Archivos relacionados con LangSmith/tracing:
- `observability/langsmith/setup_langsmith.py` — script de verificación (abajo)
- `scripts/upload_dataset.py` — sube el dataset (ver `06_evals.md`)
- `scripts/run_langsmith_eval.py` — harness `evaluate()` (ver `06_evals.md`)
- `.env` / `.env.example` — variables `LANGSMITH_*` / `LANGCHAIN_*`

Las carpetas `observability/dashboards/` y `observability/span_analysis/` están **vacías**.

---

## `observability/langsmith/setup_langsmith.py` — 74 líneas

```python
"""
Script de verificación de la conexión con LangSmith.
Envía una traza de prueba y confirma que el tracing automático está activo.
"""

import os
import sys
from dotenv import load_dotenv


def verify_langsmith_connection():
    # Cargar variables desde .env
    load_dotenv()

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    tracing = os.getenv("LANGCHAIN_TRACING_V2")
    project = os.getenv("LANGCHAIN_PROJECT", "agente-chubb-uw")

    errors = []
    if not api_key:
        errors.append("  - LANGSMITH_API_KEY no está definida en .env")
    if tracing != "true":
        errors.append(f"  - LANGCHAIN_TRACING_V2 debe ser 'true', valor actual: '{tracing}'")

    if errors:
        print("\n[ERROR] Faltan variables de entorno requeridas:")
        for error in errors:
            print(error)
        print("\nPasos para solucionarlo:")
        print("  1. Copia .env.example a .env:  cp .env.example .env")
        print("  2. Rellena LANGSMITH_API_KEY y pon LANGCHAIN_TRACING_V2=true")
        sys.exit(1)

    try:
        from langsmith import Client
        import uuid
        from datetime import datetime, timezone

        client = Client(api_key=api_key)

        # Enviar una traza mínima de prueba — si llega, la key y el proyecto funcionan
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        client.create_run(
            id=run_id,
            name="setup-verification",
            run_type="chain",
            inputs={"test": "conexión verificada"},
            start_time=now,
            project_name=project,
        )
        client.update_run(
            run_id=run_id,
            outputs={"result": "ok"},
            end_time=datetime.now(timezone.utc),
        )

        print(f"\nLangSmith conectado. Proyecto: {project}")
        print("Cualquier ejecución de LangGraph quedará trazada automáticamente.")
        print(f"\n  Traza de prueba enviada — búscala en:")
        print(f"  https://smith.langchain.com → proyecto '{project}' → run 'setup-verification'")

    except ImportError:
        print("\n[ERROR] langsmith no está instalado. Ejecuta: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] No se pudo conectar con LangSmith: {e}")
        print("\nVerifica que LANGSMITH_API_KEY es válida en https://smith.langchain.com/settings")
        sys.exit(1)


if __name__ == "__main__":
    verify_langsmith_connection()
```

---

## `grep -rn -B2 -A2` de LangSmith / LANGCHAIN_* en el repo

Comando ejecutado (excluyendo `backend/kb/index/`, binarios y `__pycache__`):
`grep -rn -B2 -A2 -E "langsmith|LANGCHAIN_TRACING|LANGCHAIN_API_KEY|LANGCHAIN_PROJECT|LANGSMITH" --include='*.py' --include='*.md' --include='.env*'`

> ⚠️ Las coincidencias en `.env` mostraban una `LANGSMITH_API_KEY` real (`lsv2_pt_...`).
> Aquí se **enmascara** el valor. El resto de coincidencias se reproduce con contexto.

```
=== .env  (VALOR REAL ENMASCARADO) ===
.env-5-AZURE_OPENAI_API_VERSION=2025-01-01-preview
.env-6-# LangSmith
.env:7:LANGSMITH_API_KEY=lsv2_pt_****************************  ← REAL, enmascarado en el snapshot
.env:8:LANGCHAIN_TRACING_V2=true
.env:9:LANGCHAIN_PROJECT=agente-chubb-uw
.env-10-# API
.env-11-API_HOST=0.0.0.0

=== .env.example ===
.env.example:7:LANGSMITH_API_KEY=              # API key de LangSmith (...)
.env.example:8:LANGCHAIN_TRACING_V2=true       # activa el tracing automático
.env.example:9:LANGCHAIN_PROJECT=agente-chubb-uw  # nombre del proyecto en LangSmith

=== CLAUDE.md ===
CLAUDE.md:17:python observability/langsmith/setup_langsmith.py

=== context/DEVELOPMENT_PLAN.md ===
DEVELOPMENT_PLAN.md-26:- [x] Crear observability/langsmith/setup_langsmith.py
DEVELOPMENT_PLAN.md-29:- [ ] Ejecutar setup_langsmith.py y verificar conexión
DEVELOPMENT_PLAN.md-51:- [x] scripts/run_langsmith_eval.py — harness langsmith.evaluate() con max_concurrency=1
DEVELOPMENT_PLAN.md-53:### Pendiente (bloqueado por LangSmith key 403)
DEVELOPMENT_PLAN.md-54:- [ ] Obtener LANGCHAIN_API_KEY válida en smith.langchain.com
DEVELOPMENT_PLAN.md-56:- [ ] Ejecutar run_langsmith_eval.py y publicar primer Experiment
DEVELOPMENT_PLAN.md-57:- [ ] Añadir config={"metadata": {"submission_id": ...}} a las llamadas LLM para trazar tokens

=== context/SESSION_LOG.md ===
SESSION_LOG.md-15:- Creado observability/langsmith/setup_langsmith.py
SESSION_LOG.md-41:- LangSmith TRACING_V2=false temporalmente (key con 403, pendiente resolución)

=== evals/evaluators.py ===
evaluators.py:139-204: def langsmith_ca01 ... langsmith_ca08  (8 funciones con firma Run/Example)
evaluators.py:202-205: ALL_EVALUATORS = [langsmith_ca01 ... langsmith_ca08]

=== observability/langsmith/setup_langsmith.py ===
setup_langsmith.py:11: def verify_langsmith_connection():
setup_langsmith.py:15: api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
setup_langsmith.py:16: tracing = os.getenv("LANGCHAIN_TRACING_V2")
setup_langsmith.py:17: project = os.getenv("LANGCHAIN_PROJECT", "agente-chubb-uw")
setup_langsmith.py:35: from langsmith import Client

=== README.md ===
README.md:14:python observability/langsmith/setup_langsmith.py

=== scripts/run_langsmith_eval.py ===  (ver 06_evals.md para el archivo completo)
run_langsmith_eval.py:23: os.environ["LANGCHAIN_TRACING_V2"] = "true"
run_langsmith_eval.py:25: from langsmith import Client, evaluate

=== scripts/upload_dataset.py ===  (ver 06_evals.md)
upload_dataset.py:17: from langsmith import Client

=== scripts/probe_sub001.py ===
probe_sub001.py:8: sys.path.insert(0, ...)   (coincidencia parcial, no LangSmith)
```

### Conclusión de observabilidad
- El código está preparado para tracing automático vía env vars (patrón correcto de LangChain).
- **No hay tracing custom** (ni callbacks, ni `@traceable`, ni `RunTree`) más allá de eso.
- `run_langsmith_eval.py` fuerza `LANGCHAIN_TRACING_V2=true` en tiempo de ejecución.
- Bloqueante conocido: la LangSmith key daba 403; nunca se ejecutó `upload_dataset.py` ni
  `run_langsmith_eval.py` con éxito → **no hay Experiments publicados en LangSmith**.
- Toda la evaluación real se hizo con un runner local (`scripts/run_e2e.py`), no con LangSmith.
