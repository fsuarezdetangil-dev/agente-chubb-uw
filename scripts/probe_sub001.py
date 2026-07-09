"""Probe rápido sobre SUB-001 para verificar fix de replace() y encoding."""
import sys, os, json, warnings, logging
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.getLogger("langsmith").setLevel(logging.ERROR)

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

graph = get_default_graph()

with open("data/samples/submissions_synthetic_all_70.json", encoding="utf-8") as f:
    subs = json.load(f)

for sub in subs[:3]:
    broker = sub["broker"] if isinstance(sub.get("broker"), str) else sub.get("broker", {}).get("name", "")
    state = {
        "submission_id": sub["submission_id"], "submission_raw": sub,
        "channel": sub["channel"], "line_of_business": sub["line_of_business"],
        "metadata": {"broker_name": broker}, "extracted_data": {}, "missing_fields": [],
        "appetite_result": {}, "risk_score": 0, "risk_flags": [], "pricing_output": {},
        "outputs": {}, "audit_log": [], "hitl_status": "none", "hitl_point": "none", "plan_json": []
    }
    config = {"configurable": {"thread_id": sub["submission_id"] + "-probe3"}}
    print(f"Probando {sub['submission_id']} ({sub['scenario_tag']})...", flush=True)
    try:
        result = graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        count = 0
        while snapshot.next and count < 3:
            node = snapshot.next[0]
            print(f"  HITL pause: {node}", flush=True)
            updates = {"hitl_status": "approved"}
            if node == "hitl_point_1":
                updates["extracted_data"] = sub["extracted_data_ground_truth"]
                updates["missing_fields"] = []
            graph.update_state(config, updates)
            result = graph.invoke(None, config=config)
            snapshot = graph.get_state(config)
            count += 1
        verdict = result.get("appetite_result", {}).get("verdict", "?")
        risk = result.get("risk_score", 0)
        prima = result.get("pricing_output", {}).get("prima_tecnica_eur", 0)
        print(f"  LOB={result['line_of_business']} | appetite={verdict} | risk={risk} | prima={prima:.0f}EUR", flush=True)
        print("  OK", flush=True)
    except Exception as e:
        err = str(e)[:300].encode("ascii", errors="replace").decode("ascii")
        print(f"  ERROR: {err}", flush=True)
        import traceback; traceback.print_exc()
