"""
Grafo principal del P&C UW Agent.
Define los nodos, aristas condicionales y los tres puntos HITL con interrupt_before.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import AgentState
from .plan_node import plan_node
from .intake_node import intake_node
from .extraction_node import extraction_node, route_after_extraction
from .appetite_node import appetite_node, route_after_appetite
from .risk_node import risk_node, route_after_risk
from .output_node import output_node


def build_graph(checkpointer=None):
    """Construye y compila el grafo. Acepta checkpointer externo para tests."""
    builder = StateGraph(AgentState)

    # Registrar nodos
    builder.add_node("plan_node",           plan_node)
    builder.add_node("submission_intake",   intake_node)
    builder.add_node("data_extraction",     extraction_node)
    builder.add_node("appetite_validation", appetite_node)
    builder.add_node("risk_assessment",     risk_node)
    builder.add_node("output_generation",   output_node)

    # Nodos HITL — vacíos: LangGraph pausará antes de ejecutarlos (interrupt_before)
    builder.add_node("hitl_point_1", lambda s: s)
    builder.add_node("hitl_point_2", lambda s: s)
    builder.add_node("hitl_point_3", lambda s: s)

    # Flujo principal
    builder.set_entry_point("plan_node")
    builder.add_edge("plan_node",           "submission_intake")
    builder.add_edge("submission_intake",   "data_extraction")

    # Arista condicional 1: datos incompletos → HITL-1, completos → appetite
    builder.add_conditional_edges(
        "data_extraction",
        route_after_extraction,
        {"hitl_point_1": "hitl_point_1", "appetite_validation": "appetite_validation"},
    )
    builder.add_edge("hitl_point_1", "appetite_validation")

    # Arista condicional 2: fuera/revision → HITL-2, dentro → risk
    builder.add_conditional_edges(
        "appetite_validation",
        route_after_appetite,
        {"hitl_point_2": "hitl_point_2", "risk_assessment": "risk_assessment"},
    )
    builder.add_edge("hitl_point_2", "risk_assessment")

    # Arista condicional 3: risk alto → HITL-3, bajo → output
    builder.add_conditional_edges(
        "risk_assessment",
        route_after_risk,
        {"hitl_point_3": "hitl_point_3", "output_generation": "output_generation"},
    )
    builder.add_edge("hitl_point_3", "output_generation")

    builder.add_edge("output_generation", END)

    # Compilar con interrupt_before en los tres puntos HITL
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_point_1", "hitl_point_2", "hitl_point_3"],
    )


def get_default_graph():
    """Instancia el grafo con checkpointer SQLite persistente."""
    import sqlite3
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer=checkpointer)


if __name__ == "__main__":
    # Smoke test rápido con una submission mínima
    graph = get_default_graph()

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

    config = {"configurable": {"thread_id": "TEST-001"}}
    result = graph.invoke(initial_state, config=config)

    print("\n=== Smoke test completado ===")
    print(f"Submission: {result['submission_id']}")
    print(f"Plan JSON: {len(result['plan_json'])} pasos")
    print(f"Extracted fields: {list(result['extracted_data'].keys())}")
    print(f"Appetite verdict: {result['appetite_result'].get('verdict')}")
    print(f"Risk score: {result['risk_score']}")
    print(f"Prima técnica: {result['pricing_output'].get('prima_tecnica_eur')} EUR")
    print(f"Audit log: {len(result['audit_log'])} entradas")
    print(f"HITL status: {result['hitl_status']}")
    print(f"\nOutputs:")
    for k, v in result['outputs'].items():
        print(f"  {k}: {v[:80]}...")
