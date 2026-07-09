"""
Test de Fase 3E: Output Generation con Reflection pattern.
Prueba 3 escenarios: STP, HITL-3 (riesgo alto), fuera de apetito.
Verifica CA-07 (LLM-Judge score ≥ 85/100).
Ejecutar desde la raíz: python scripts/test_fase3e.py
"""

import sys, os, json, warnings, logging
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.getLogger("langsmith").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

graph = get_default_graph()


def build_state(sub: dict) -> AgentState:
    broker = sub["broker"] if isinstance(sub.get("broker"), str) else sub.get("broker", {}).get("name", "")
    return {
        "submission_id": sub["submission_id"],
        "submission_raw": sub,
        "channel": sub["channel"],
        "line_of_business": sub["line_of_business"],
        "metadata": {"broker_name": broker},
        "extracted_data": {},
        "missing_fields": [],
        "appetite_result": {},
        "risk_score": 0,
        "risk_flags": [],
        "pricing_output": {},
        "outputs": {},
        "audit_log": [],
        "hitl_status": "none",
        "hitl_point": "none",
        "plan_json": [],
    }


def run_full_flow(sub: dict) -> dict:
    """Ejecuta el flujo completo reanudando automáticamente todos los HITL."""
    config = {"configurable": {"thread_id": sub["submission_id"] + "-3E"}}
    result = graph.invoke(build_state(sub), config=config)
    snapshot = graph.get_state(config)
    hitl_count = 0
    while snapshot.next and hitl_count < 3:
        node = snapshot.next[0]
        updates = {"hitl_status": "approved"}
        if node == "hitl_point_1":
            updates["extracted_data"] = sub["extracted_data_ground_truth"]
            updates["missing_fields"] = []
        graph.update_state(config, updates)
        result = graph.invoke(None, config=config)
        snapshot = graph.get_state(config)
        hitl_count += 1
    return result


# Cargar datasets
with open("data/samples/submissions_property_30.json", encoding="utf-8") as f:
    prop = json.load(f)
with open("data/samples/submissions_casualty_30.json", encoding="utf-8") as f:
    cas = json.load(f)

escenarios = [
    ("STP casualty — academia formación",
     next(s for s in cas if s["expected_hitl_trigger"] == "STP_dentro_apetito")),
    ("HITL-3 property — químicos revisión",
     next(s for s in prop if s["expected_hitl_trigger"] == "HITL-3_referir_senior")),
    ("HITL-2 property — fuera apetito",
     next(s for s in prop if s["expected_hitl_trigger"] == "HITL-2_declinar")),
]

ca07_results = []

for nombre, sub in escenarios:
    print(f"\n{'='*65}")
    print(f"ESCENARIO: {nombre} | {sub['submission_id']}")
    print(f"{'='*65}")

    result = run_full_flow(sub)

    outputs = result.get("outputs", {})
    quality = outputs.get("_quality", {})
    out_log = next((e for e in result["audit_log"] if e["node"] == "output_generation"), {})
    refl_log = out_log.get("reflection_log", [])

    score = quality.get("llm_judge_score", 0)
    ca07_ok = quality.get("ca07_passed", False)
    ca07_results.append(ca07_ok)

    print(f"\n--- REFLECTION LOG ---")
    for r in refl_log:
        if r["action"] == "reflection":
            scores = r.get("scores", {})
            print(f"  Pasada {r['pass']} | Score total: {r['total_score']}/100 | Aprobado: {r['approved']}")
            for dim, val in scores.items():
                print(f"    {dim}: {val}/20")
            if r.get("critique") and r["critique"] != "ninguno":
                print(f"  Crítica: {r['critique'][:150]}")
        else:
            print(f"  Pasada {r['pass']}: {r['action']}")

    print(f"\n  CA-07 LLM-Judge score: {score}/100 {'✓' if ca07_ok else '✗'}")
    print(f"  Ciclos de reflexión: {quality.get('reflection_cycles', 0)}")
    print(f"  Tokens output+reflection: {out_log.get('tokens_used_total', '?')}")

    print(f"\n--- RISK SUMMARY (primeros 400 chars) ---")
    print(outputs.get("risk_summary", "")[:400])

    print(f"\n--- QUOTE DRAFT (primeros 300 chars) ---")
    print(outputs.get("quote_draft", "")[:300])

    print(f"\n--- BROKER COMM (primeros 300 chars) ---")
    print(outputs.get("broker_comm", "")[:300])

    # CA-08: time-to-quote (diferencia entre primer y último timestamp del audit_log)
    log = result.get("audit_log", [])
    if len(log) >= 2:
        from datetime import datetime, timezone
        t0 = datetime.fromisoformat(log[0]["timestamp"])
        t1 = datetime.fromisoformat(log[-1]["timestamp"])
        elapsed = (t1 - t0).total_seconds()
        ca08_ok = elapsed < 240  # < 4 minutos
        print(f"\n  CA-08 Time-to-quote: {elapsed:.1f}s {'✓' if ca08_ok else '✗ (>4min)'}")

print(f"\n{'='*65}")
print(f"RESUMEN CA-07: {sum(ca07_results)}/{len(ca07_results)} outputs aprobados ({sum(ca07_results)/len(ca07_results):.0%})")
