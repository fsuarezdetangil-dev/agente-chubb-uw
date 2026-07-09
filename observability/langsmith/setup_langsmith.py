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
