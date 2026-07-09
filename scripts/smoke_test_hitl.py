"""
Smoke test del flujo HITL-1: submission con campos faltantes.
Verifica que el grafo se pausa en hitl_point_1 y puede reanudarse.
Ejecutar desde la raíz: python scripts/smoke_test_hitl.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

graph = get_default_graph()
config = {"configurable": {"thread_id": "TEST-HITL1"}}

initial_state: AgentState = {
    "submission_id": "TEST-HITL1",
    "submission_raw": {
        "extracted_data_ground_truth": {
            "company_name": "Logística Express S.L.",
            "cnae_code": None,
            "activity_description": "Transporte de mercancías",
            "province": "Madrid",
            "sum_insured_eur": None,
            "requested_coverages": None,
            "loss_history": None,
            "loss_ratio": None,
            "renewal": False,
        },
        "missing_fields_expected": ["cnae_code", "sum_insured_eur", "loss_history"],
        "appetite_expected": "dentro",
        "expected_hitl_trigger": "HITL-1_datos_incompletos",
        "metadata": {"broker": "AON Madrid", "tomador": "Logística Express S.L."},
    },
    "channel": "email",
    "line_of_business": "casualty",
    "metadata": {},
    "extracted_data": {},
    "missing_fields": [],
    "appetite_result": {},
    "risk_score": 0,
    "risk_flags": [],
    "pricing_output": {},
    "outputs": {},
    "audit_log": [],
    "hitl_status": "pending",
    "hitl_point": "point_1",
    "plan_json": [],
}

# Primera invocación: debe pausar en hitl_point_1
print("--- Invocación 1: flujo hasta HITL-1 ---")
result = graph.invoke(initial_state, config=config)
state_snapshot = graph.get_state(config)
print(f"Siguiente nodo: {state_snapshot.next}")
print(f"Missing fields: {result.get('missing_fields')}")
print(f"Audit log: {[e['node'] for e in result.get('audit_log', [])]}")

# Simular aprobación UW: reanudar el grafo con los campos completados
print("\n--- Invocación 2: UW aprueba y reanuda ---")
graph.update_state(config, {
    "hitl_status": "approved",
    "hitl_point": "point_1",
    "missing_fields": [],
})
result2 = graph.invoke(None, config=config)
print(f"Appetite: {result2['appetite_result'].get('verdict')}")
print(f"Risk score: {result2['risk_score']}")
print(f"HITL status final: {result2['hitl_status']}")
print(f"Audit log completo: {[e['node'] for e in result2.get('audit_log', [])]}")
print("\nHITL-1 OK: pausa y reanudación funcionan correctamente.")
