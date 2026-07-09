"""
Test de Fase 3A: Plan JSON Node + Submission Intake con LLM real.
Ejecutar desde la raíz: python scripts/test_fase3a.py
"""

import sys, os, json, warnings, logging
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.getLogger("langsmith").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

# Cargar una submission STP de property del dataset real
with open("data/samples/submissions_property_30.json", encoding="utf-8") as f:
    subs = json.load(f)

# Buscar una STP property completa
sub = next(s for s in subs if s["expected_hitl_trigger"] == "STP_dentro_apetito")
print(f"Submission seleccionada: {sub['submission_id']} | {sub['scenario_tag']}")
email = sub["email_raw"]
email_preview = email.get("body", str(email))[:300] if isinstance(email, dict) else str(email)[:300]
print(f"Email (primeros 300 chars): {email_preview}\n")

graph = get_default_graph()
config = {"configurable": {"thread_id": sub["submission_id"] + "-3A"}}

initial_state: AgentState = {
    "submission_id": sub["submission_id"],
    "submission_raw": sub,
    "channel": sub["channel"],
    "line_of_business": sub["line_of_business"],
    "metadata": {},
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

result = graph.invoke(initial_state, config=config)

print("=== PLAN JSON NODE ===")
for step in result["plan_json"]:
    print(f"  Step {step['step']} [{step['node']}]: {step.get('description','')}")
    if step.get("anticipation"):
        print(f"    → {step['anticipation']}")

print("\n=== SUBMISSION INTAKE (Node 1) ===")
print(f"  LOB clasificada:    {result['line_of_business']} (ground-truth: {sub['line_of_business']})")
print(f"  Canal:              {result['channel']}")
print(f"  Broker:             {result['metadata'].get('broker_name','?')}")
print(f"  Tomador:            {result['metadata'].get('tomador','?')}")
print(f"  Renovación:         {result['metadata'].get('renewal','?')}")
print(f"  Confianza clasif.:  {result['metadata'].get('classification_confidence','?')}")
print(f"  Razonamiento:       {result['metadata'].get('classification_reasoning','?')[:120]}")

lob_ok = result["line_of_business"] == sub["line_of_business"]
print(f"\n  CA-01 LOB correcta: {'✓' if lob_ok else '✗'}")

print("\n=== AUDIT LOG ===")
for entry in result["audit_log"]:
    tokens = entry.get("tokens_used", {})
    t_str = f" | tokens: {tokens}" if tokens else " | stub"
    print(f"  {entry['node']} [{entry['status']}]{t_str}")
