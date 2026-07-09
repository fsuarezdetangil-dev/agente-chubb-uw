"""
Ejecuta la evaluación formal del agente contra el golden dataset en LangSmith.
Ejecutar desde la raíz: python scripts/run_langsmith_eval.py

Prerequisitos:
  1. LANGCHAIN_API_KEY válida en .env (sin error 403)
  2. Dataset "chubb-uw-golden-72" subido (python scripts/upload_dataset.py)

Qué hace:
  - Carga el grafo con checkpointer SQLite temporal (thread_id único por run)
  - Para cada ejemplo del dataset invoca el agente y auto-reanuda HITL
  - Evalúa CA-01 a CA-08 con los evaluadores de evals/evaluators.py
  - Publica resultados en LangSmith Experiments
"""

import sys, os, json, warnings, logging, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.getLogger("langsmith").setLevel(logging.WARNING)

from dotenv import load_dotenv
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "true"

from langsmith import Client, evaluate
from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from evals.evaluators import ALL_EVALUATORS
from langgraph.checkpoint.sqlite import SqliteSaver

DATASET_NAME = "chubb-uw-golden-72"


def _build_state(inputs: dict) -> AgentState:
    broker = inputs.get("broker", "")
    if isinstance(broker, dict):
        broker = broker.get("name", "")
    return {
        "submission_id":    inputs.get("submission_id", ""),
        "submission_raw":   inputs,
        "channel":          inputs.get("channel", "email"),
        "line_of_business": inputs.get("line_of_business", "property"),
        "metadata":         {"broker_name": broker},
        "extracted_data":   {},
        "missing_fields":   [],
        "appetite_result":  {},
        "risk_score":       0,
        "risk_flags":       [],
        "pricing_output":   {},
        "outputs":          {},
        "audit_log":        [],
        "hitl_status":      "none",
        "hitl_point":       "none",
        "plan_json":        [],
    }


def _resume_hitl(graph, result, config, reference: dict) -> tuple[dict, list[str]]:
    """Auto-reanuda HITL inyectando ground truth en HITL-1."""
    snapshot = graph.get_state(config)
    hitl_nodes = []
    count = 0
    while snapshot.next and count < 3:
        node = snapshot.next[0]
        hitl_nodes.append(node)
        updates = {"hitl_status": "approved"}
        if node == "hitl_point_1":
            # Capturar lo que Node 2 detectó como faltante ANTES de resolver el
            # HITL, para que CA-03 lo lea al final (el resume vacía missing_fields
            # al inyectar el ground truth aprobado por el UW).
            updates["missing_fields_at_extraction"] = snapshot.values.get("missing_fields", [])
            updates["extracted_data"] = reference.get("extracted_data_ground_truth", {})
            updates["missing_fields"] = []
        graph.update_state(config, updates)
        result = graph.invoke(None, config=config)
        snapshot = graph.get_state(config)
        count += 1
    return result, hitl_nodes


def agent_fn(inputs: dict) -> dict:
    """Función del agente para LangSmith evaluate(). Incluye _hitl_triggered en outputs."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    graph = build_graph(checkpointer=SqliteSaver(conn))

    sid = inputs.get("submission_id", "unknown")
    config = {"configurable": {"thread_id": sid + "-ls"}}
    state = _build_state(inputs)

    # La referencia se pasa en inputs bajo la clave "__reference" (workaround LangSmith)
    reference = inputs.get("__reference", {})

    result = graph.invoke(state, config=config)
    result, hitl_triggered = _resume_hitl(graph, result, config, reference)

    conn.close()
    result["_hitl_triggered"] = hitl_triggered
    return result


def main():
    client = Client()

    # Verificar conexión y dataset
    datasets = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if not datasets:
        print(f"Dataset '{DATASET_NAME}' no encontrado.")
        print("Ejecuta primero: python scripts/upload_dataset.py")
        sys.exit(1)

    print(f"Dataset encontrado: {datasets[0].id}")
    print("Lanzando evaluacion en LangSmith...\n")

    results = evaluate(
        agent_fn,
        data=DATASET_NAME,
        evaluators=ALL_EVALUATORS,
        experiment_prefix="chubb-uw-e2e",
        description="Pasada E2E automatica — CA-01 a CA-08",
        max_concurrency=1,         # llamadas secuenciales para evitar rate limit Azure
    )

    print("\n=== RESUMEN ===")
    for r in results:
        # langsmith 0.9.x devuelve dicts al iterar; versiones previas, objetos con atributos
        eval_results = r.evaluation_results if hasattr(r, "evaluation_results") else r.get("evaluation_results", {})
        run = r.run if hasattr(r, "run") else r.get("run")
        results_list = (eval_results or {}).get("results", []) if isinstance(eval_results, dict) else getattr(eval_results, "results", [])
        scores = {}
        for e in results_list:
            key   = e["key"]   if isinstance(e, dict) else getattr(e, "key", None)
            score = e["score"] if isinstance(e, dict) else getattr(e, "score", None)
            scores[key] = score
        run_name = run.get("name") if isinstance(run, dict) else getattr(run, "name", None)
        print(f"  {run_name}: {scores}")

    print(f"\nResultados publicados en LangSmith Experiments.")
    print(f"URL: https://smith.langchain.com")


if __name__ == "__main__":
    main()
