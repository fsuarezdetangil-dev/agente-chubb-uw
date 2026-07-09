"""
Inicialización de la capa de observabilidad con Phoenix Arize.
Llamar a init_tracing() UNA SOLA VEZ antes de invocar el grafo LangGraph.

Variables de entorno requeridas (ver .env.example):
  PHOENIX_API_KEY              — clave de app.phoenix.arize.com
  PHOENIX_PROJECT_NAME         — nombre del proyecto (default: agente-chubb-uw)
  PHOENIX_COLLECTOR_ENDPOINT   — endpoint OTLP (default: nube Arize)
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

_TRACING_INITIALIZED = False


def init_tracing() -> bool:
    """
    Registra el TracerProvider de Phoenix e instrumenta LangChain/LangGraph.
    Devuelve True si el tracing quedó activo, False si se omitió por falta de config.
    """
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return True

    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    project = os.getenv("PHOENIX_PROJECT_NAME", "agente-chubb-uw").strip()
    endpoint = os.getenv(
        "PHOENIX_COLLECTOR_ENDPOINT",
        "https://app.phoenix.arize.com/v1/traces",
    ).strip()

    if not api_key:
        logger.warning(
            "[Phoenix] PHOENIX_API_KEY no definida — tracing desactivado. "
            "Añádela en .env para enviar trazas a app.phoenix.arize.com"
        )
        return False

    try:
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor

        tracer_provider = register(
            project_name=project,
            endpoint=endpoint,
            set_global_tracer_provider=True,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        _TRACING_INITIALIZED = True
        logger.info(
            f"[Phoenix] Tracing activo — proyecto '{project}' → {endpoint}"
        )
        return True

    except ImportError as exc:
        logger.error(
            f"[Phoenix] Dependencia no instalada: {exc}. "
            "Ejecuta: pip install arize-phoenix-otel openinference-instrumentation-langchain opentelemetry-sdk"
        )
        return False
    except Exception as exc:
        logger.error(f"[Phoenix] Error al inicializar tracing: {exc}")
        return False
