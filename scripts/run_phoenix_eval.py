"""
Pasada E2E como Experimento de Phoenix Arize.
Corre el agente sobre el dataset "chubb-uw-golden-72" y registra los 8 CAs
como evaluaciones por submission. Cada ejecución genera un experimento nuevo
en Phoenix → histórico comparativo de runs.

Ejecutar desde la raíz: python scripts/run_phoenix_eval.py [--name mi-experimento]

Requiere en .env:
  PHOENIX_API_KEY, PHOENIX_COLLECTOR_ENDPOINT, AZURE_OPENAI_*
"""

import sys, os, json, time, warnings, logging, argparse
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.getLogger("langsmith").setLevel(logging.ERROR)

from dotenv import load_dotenv
load_dotenv()

import httpx

from observability.phoenix.init_tracing import init_tracing
init_tracing()

from opentelemetry import trace as otel_trace

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState
from evals.evaluators import (
    eval_ca01, eval_ca02, eval_ca03, eval_ca04,
    eval_ca05, eval_ca06, eval_ca07, eval_ca08,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATASET_NAME = "chubb-uw-golden-72"


# ── Phoenix REST helpers ───────────────────────────────────────────────────────

def _base_url() -> str:
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    return endpoint.replace("/v1/traces", "").rstrip("/")


def _headers() -> dict:
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_dataset(client: httpx.Client) -> tuple[str, list[dict]]:
    """Devuelve (dataset_id, lista de ejemplos)."""
    r = client.get("/v1/datasets")
    r.raise_for_status()
    ds = next((d for d in r.json().get("data", []) if d.get("name") == DATASET_NAME), None)
    if not ds:
        print(f"[ERROR] Dataset '{DATASET_NAME}' no encontrado.")
        print("Ejecuta primero: python scripts/upload_phoenix_dataset.py")
        sys.exit(1)
    dataset_id = ds["id"]
    r2 = client.get(f"/v1/datasets/{dataset_id}/examples")
    r2.raise_for_status()
    examples = r2.json()["data"]["examples"]
    logger.info(f"Dataset '{DATASET_NAME}': {len(examples)} ejemplos")
    return dataset_id, examples


def create_experiment(client: httpx.Client, dataset_id: str, name: str) -> str:
    payload = {
        "name":     name,
        "metadata": {
            "timestamp": _now(),
            "model":     os.getenv("AZURE_OPENAI_DEPLOYMENT", "unknown"),
        },
    }
    r = client.post(f"/v1/datasets/{dataset_id}/experiments", json=payload)
    r.raise_for_status()
    exp_id = r.json()["data"]["id"]
    logger.info(f"Experimento creado: {name} (id={exp_id})")
    return exp_id


def log_run(client: httpx.Client, exp_id: str, example_id: str,
            output: dict, start_time: str, end_time: str,
            error: str | None = None, trace_id: str | None = None) -> str:
    payload = {
        "dataset_example_id": example_id,
        "output":             output,
        "repetition_number":  1,
        "start_time":         start_time,
        "end_time":           end_time,
        "error":              error,
        "trace_id":           trace_id,
    }
    r = client.post(f"/v1/experiments/{exp_id}/runs", json=payload)
    r.raise_for_status()
    return r.json()["data"]["id"]


def log_evaluations(client: httpx.Client, run_id: str, scores: dict):
    """Registra un evaluation por cada CA score."""
    ts = _now()
    for name, score in scores.items():
        if score is None:
            continue
        payload = {
            "experiment_run_id": run_id,
            "name":              name,
            "annotator_kind":    "CODE",
            "start_time":        ts,
            "end_time":          ts,
            "result": {
                "score":       float(score),
                "label":       "pass" if float(score) >= 0.5 else "fail",
                "explanation": f"{name}={score}",
            },
        }
        r = client.post("/v1/experiment_evaluations", json=payload)
        if r.status_code not in (200, 201):
            logger.warning(f"  eval {name}: {r.status_code} {r.text[:200]}")


# ── agente ─────────────────────────────────────────────────────────────────────

graph = get_default_graph()


def build_state(sub: dict) -> AgentState:
    broker = sub["broker"] if isinstance(sub.get("broker"), str) \
             else sub.get("broker", {}).get("name", "")
    return {
        "submission_id":    sub["submission_id"],
        "submission_raw":   sub,
        "channel":          sub["channel"],
        "line_of_business": sub["line_of_business"],
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


_tracer = otel_trace.get_tracer("run_phoenix_eval")


def run_submission(sub: dict) -> tuple[dict, list[str], list[str], str]:
    """Ejecuta el agente. Devuelve (result, hitl_triggered, missing_pre_hitl, trace_id_hex)."""
    config = {"configurable": {"thread_id": sub["submission_id"] + "-px"}}

    with _tracer.start_as_current_span(f"submission/{sub['submission_id']}") as root_span:
        result = graph.invoke(build_state(sub), config=config)
        missing_pre_hitl = list(result.get("missing_fields", []))
        hitl_triggered = []
        snapshot = graph.get_state(config)
        count = 0
        while snapshot.next and count < 3:
            node = snapshot.next[0]
            hitl_triggered.append(node)
            updates = {"hitl_status": "approved"}
            if node == "hitl_point_1":
                updates["extracted_data"] = sub.get("extracted_data_ground_truth", {})
                updates["missing_fields"] = []
            graph.update_state(config, updates)
            result = graph.invoke(None, config=config)
            snapshot = graph.get_state(config)
            count += 1

        # Capturar trace_id en formato hexadecimal de 32 chars (formato OTEL estándar)
        ctx = root_span.get_span_context()
        trace_id_hex = format(ctx.trace_id, "032x") if ctx.is_valid else None

    return result, hitl_triggered, missing_pre_hitl, trace_id_hex


def score_submission(result: dict, reference: dict,
                     hitl_triggered: list[str], missing_pre_hitl: list[str]) -> dict:
    ca07_ok, ca07_score = eval_ca07(result)
    ca08_ok, ca08_secs  = eval_ca08(result)
    ca02 = eval_ca02(result, reference)
    return {
        "ca01_lob_accuracy":       float(eval_ca01(result, reference)),
        "ca02_extraction_accuracy": ca02,
        "ca03_missing_fields":      float(eval_ca03(
                                        {"missing_fields_at_extraction": missing_pre_hitl, **result},
                                        reference)),
        "ca04_appetite_verdict":    float(eval_ca04(result, reference)),
        "ca05_rag_citations":       float(eval_ca05(result)),
        "ca06_hitl_routing":        float(eval_ca06(result, reference, hitl_triggered)),
        "ca07_llm_judge":           float(ca07_ok),
        "ca07_score":               float(ca07_score) if ca07_score is not None else None,
        "ca08_time_to_quote":       float(ca08_ok) if ca08_ok is not None else None,
        "ca08_secs":                ca08_secs,
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=None,
                        help="Nombre del experimento (default: e2e-YYYYMMDD-HHMMSS)")
    args = parser.parse_args()
    exp_name = args.name or f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] PHOENIX_API_KEY no definida en .env")
        sys.exit(1)

    base_url = _base_url()
    print(f"\nPhoenix : {base_url}")
    print(f"Experimento: {exp_name}\n")

    with httpx.Client(base_url=base_url, headers=_headers(), timeout=30) as phoenix:

        dataset_id, examples = get_dataset(phoenix)
        # Construir mapa example_id → sub data para ejecución
        exp_id = create_experiment(phoenix, dataset_id, exp_name)

        ok_count = err_count = 0

        for idx, example in enumerate(examples):
            inp = example.get("input", {})
            ref = example.get("output", {})
            # El dataset tiene submission_id en metadata o en input
            sid = inp.get("submission_id") or example.get("metadata", {}).get("submission_id", f"ex-{idx}")
            # Reconstruir sub completo: input + output (ground truth)
            sub = {**inp, **ref}

            start_time = _now()
            try:
                t0 = time.time()
                result, hitl_triggered, missing_pre_hitl, trace_id = run_submission(sub)
                elapsed = round(time.time() - t0, 1)

                scores = score_submission(result, ref, hitl_triggered, missing_pre_hitl)

                output_payload = {
                    "submission_id":    sid,
                    "line_of_business": result.get("line_of_business"),
                    "appetite_verdict": result.get("appetite_result", {}).get("verdict"),
                    "risk_score":       result.get("risk_score"),
                    "prima_eur":        result.get("pricing_output", {}).get("prima_tecnica_eur"),
                    "hitl_triggered":   hitl_triggered,
                    "wall_secs":        elapsed,
                    **{k: v for k, v in scores.items()},
                }

                end_time = _now()
                run_id = log_run(phoenix, exp_id, example["id"],
                                 output_payload, start_time, end_time,
                                 trace_id=trace_id)

                # Solo enviar métricas numéricas como evaluaciones (excluir secs/score auxiliares)
                eval_scores = {
                    k: v for k, v in scores.items()
                    if not k.endswith("_secs")
                }
                log_evaluations(phoenix, run_id, eval_scores)

                checks = "".join([
                    "✓" if scores["ca01_lob_accuracy"]      else "✗",
                    "✓" if (scores["ca02_extraction_accuracy"] or 0) >= 0.8 else "✗",
                    "✓" if scores["ca03_missing_fields"]     else "✗",
                    "✓" if scores["ca04_appetite_verdict"]   else "✗",
                    "✓" if scores["ca05_rag_citations"]      else "✗",
                    "✓" if scores["ca06_hitl_routing"]       else "✗",
                    "✓" if scores["ca07_llm_judge"]          else "✗",
                    "✓" if (scores["ca08_time_to_quote"] or 0) else "✗",
                ])
                print(f"[{idx+1:02d}/{len(examples)}] {sid} | [{checks}] {elapsed}s")
                ok_count += 1

            except Exception as exc:
                end_time = _now()
                err_msg = str(exc)[:300]
                print(f"[{idx+1:02d}/{len(examples)}] {sid} | ERROR: {err_msg}")
                try:
                    log_run(phoenix, exp_id, example["id"],
                            {"submission_id": sid}, start_time, end_time, error=err_msg)
                except Exception:
                    pass
                err_count += 1

    print(f"\n{'='*60}")
    print(f"Experimento '{exp_name}': {ok_count} OK, {err_count} errores")
    print(f"Ver en Phoenix: {base_url}/experiments/{exp_id}")


if __name__ == "__main__":
    main()
