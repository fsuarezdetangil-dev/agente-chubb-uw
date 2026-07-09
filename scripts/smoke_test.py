"""
Smoke test del grafo completo con una submission STP mínima.
Ejecutar desde la raíz del proyecto: python scripts/smoke_test.py
"""

import sys
import os

# Añadir la raíz al path para que los imports relativos de backend/ funcionen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

initial_state: AgentState = {
    "submission_id": "TEST-001",
    "submission_raw": {
        "extracted_data_ground_truth": {
            "company_name": "Aceros del Norte S.A.",
            "cnae_code": "2410",
            "activity_description": "Fabricación de productos de acero",
            "province": "Bilbao",
            "sum_insured_eur": 5000000,
            "requested_coverages": ["incendio", "robo"],
            "loss_history": "sin siniestros en 3 años",
            "loss_ratio": 0.0,
            "renewal": True,
        },
        "missing_fields_expected": [],
        "appetite_expected": "dentro",
        "expected_hitl_trigger": "STP_dentro_apetito",
        "metadata": {"broker": "Marsh Madrid", "tomador": "Aceros del Norte S.A."},
    },
    "channel": "email",
    "line_of_business": "property",
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

graph = get_default_graph()
config = {"configurable": {"thread_id": "TEST-001"}}
result = graph.invoke(initial_state, config=config)

print("\n=== Smoke test completado ===")
print(f"Submission:      {result['submission_id']}")
print(f"Plan JSON:       {len(result['plan_json'])} pasos")
print(f"Extracted:       {list(result['extracted_data'].keys())}")
print(f"Appetite:        {result['appetite_result'].get('verdict')}")
print(f"Risk score:      {result['risk_score']}/100")
print(f"Risk flags:      {result['risk_flags']}")
print(f"Prima técnica:   {result['pricing_output'].get('prima_tecnica_eur')} EUR")
print(f"HITL status:     {result['hitl_status']}")
print(f"Audit log:       {len(result['audit_log'])} nodos ejecutados")
print(f"\nOutputs:")
for k, v in result["outputs"].items():
    print(f"  {k}: {str(v)[:90]}...")
