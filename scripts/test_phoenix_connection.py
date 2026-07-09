"""
CA-01 (Phoenix): Verifica la conexión con app.phoenix.arize.com y envía una traza de prueba.
Ejecutar desde la raíz: python scripts/test_phoenix_connection.py

Criterio de aceptación:
  - El script termina sin errores
  - La traza aparece en app.phoenix.arize.com bajo el proyecto agente-chubb-uw
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def test_phoenix_connection():
    api_key  = os.getenv("PHOENIX_API_KEY", "").strip()
    project  = os.getenv("PHOENIX_PROJECT_NAME", "agente-chubb-uw").strip()
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "https://app.phoenix.arize.com/v1/traces").strip()

    # Validar variables de entorno
    errors = []
    if not api_key:
        errors.append("  - PHOENIX_API_KEY no está definida en .env")
    if not project:
        errors.append("  - PHOENIX_PROJECT_NAME no está definida en .env")

    if errors:
        print("\n[ERROR] Faltan variables de entorno requeridas:")
        for e in errors:
            print(e)
        print("\nPasos para solucionarlo:")
        print("  1. Copia .env.example a .env:  copy .env.example .env")
        print("  2. Rellena PHOENIX_API_KEY con tu clave de app.phoenix.arize.com")
        sys.exit(1)

    # Inicializar tracing Phoenix
    try:
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor
        import opentelemetry.trace as otel_trace
    except ImportError as exc:
        print(f"\n[ERROR] Dependencia no instalada: {exc}")
        print("Ejecuta: pip install arize-phoenix-otel openinference-instrumentation-langchain opentelemetry-sdk")
        sys.exit(1)

    print(f"\nConectando con Phoenix Arize...")
    print(f"  Proyecto  : {project}")
    print(f"  Endpoint  : {endpoint}")

    try:
        tracer_provider = register(
            project_name=project,
            endpoint=endpoint,
            set_global_tracer_provider=True,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception as exc:
        print(f"\n[ERROR] No se pudo inicializar Phoenix: {exc}")
        sys.exit(1)

    # Enviar una traza de prueba manual via OpenTelemetry
    try:
        tracer = otel_trace.get_tracer("test_phoenix_connection")
        with tracer.start_as_current_span("setup-verification") as span:
            span.set_attribute("test.status", "ok")
            span.set_attribute("project", project)
            print("\nTraza de prueba enviada.")

        # Forzar flush antes de salir
        tracer_provider.force_flush(timeout_millis=10_000)

        print(f"\n[OK] Phoenix conectado correctamente.")
        print(f"     Busca la traza en:")
        print(f"     https://app.phoenix.arize.com → proyecto '{project}' → span 'setup-verification'")

    except Exception as exc:
        print(f"\n[ERROR] Fallo al enviar traza: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    test_phoenix_connection()
