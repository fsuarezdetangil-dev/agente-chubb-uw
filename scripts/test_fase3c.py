"""
Test de Fase 3C: Appetite & Validation con RAG real.
Prueba 4 escenarios: dentro (property), dentro (casualty), fuera, revision.
Verifica CA-04 (veredicto correcto) y CA-05 (citas RAG presentes).
Ejecutar desde la raíz: python scripts/test_fase3c.py
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
    gt = sub.get("extracted_data_ground_truth", {})
    return {
        "submission_id": sub["submission_id"],
        "submission_raw": sub,
        "channel": sub["channel"],
        "line_of_business": sub["line_of_business"],
        "metadata": {"broker_name": broker, "tomador": gt.get("company_name", "")},
        # Inyectamos ground-truth directamente en extracted_data para aislar el test de Node 3
        "extracted_data": gt,
        "missing_fields": [],  # forzado a vacío: inyectamos ground-truth, no queremos HITL-1
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


# Cargar datasets
with open("data/samples/submissions_property_30.json", encoding="utf-8") as f:
    prop = json.load(f)
with open("data/samples/submissions_casualty_30.json", encoding="utf-8") as f:
    cas = json.load(f)

def first(subs, appetite, hitl="STP_dentro_apetito"):
    return next(s for s in subs if s["appetite_expected"] == appetite and not s.get("missing_fields_expected"))

escenarios = [
    ("STP property — dentro apetito",  first(prop, "dentro"),   "dentro"),
    ("STP casualty — dentro apetito",  first(cas,  "dentro"),   "dentro"),
    ("Property — fuera de apetito",    next(s for s in prop if s["appetite_expected"] == "fuera"), "fuera"),
    ("Property — requiere revision",   next(s for s in prop if s["appetite_expected"] == "revision"), "revision"),
]

ca04_results = []

for nombre, sub, expected_verdict in escenarios:
    print(f"\n{'='*65}")
    print(f"ESCENARIO: {nombre}")
    print(f"  {sub['submission_id']} | {sub['scenario_tag']} | LOB: {sub['line_of_business']}")
    gt = sub.get("extracted_data_ground_truth", {})
    print(f"  Actividad: {gt.get('activity_description','?')} | SA: {gt.get('sum_insured_eur','?')} EUR")
    print(f"{'='*65}")

    config = {"configurable": {"thread_id": sub["submission_id"] + "-3C"}}
    initial = build_state(sub)

    # Primera invocación: puede pausar en HITL-1 si extraction_node detecta campos faltantes
    result = graph.invoke(initial, config=config)
    snapshot = graph.get_state(config)

    # Si se paró en HITL-1, simular UW completando datos con el ground-truth e injecting
    if snapshot.next and "hitl_point_1" in snapshot.next:
        graph.update_state(config, {
            "extracted_data": sub["extracted_data_ground_truth"],
            "missing_fields": [],
            "hitl_status": "approved",
        })
        result = graph.invoke(None, config=config)
        snapshot = graph.get_state(config)

    app = result.get("appetite_result", {})
    verdict     = app.get("verdict", "?")
    confidence  = app.get("confidence", "?")
    citations   = app.get("rag_citations", [])
    chunks_ret  = app.get("retrieved_chunks", [])

    verdict_ok = verdict == expected_verdict
    ca04_results.append(verdict_ok)

    print(f"  Veredicto LLM:   {verdict} (esperado: {expected_verdict}) {'✓' if verdict_ok else '✗'}")
    print(f"  Confianza:       {confidence}")
    print(f"  Justificación:   {app.get('justification','')[:150]}")
    print(f"  Limitaciones:    {app.get('data_limitations','')[:100]}")
    print(f"  Siguiente nodo:  {snapshot.next}")

    # CA-05: verificar que hay citas RAG
    ca05_ok = len(citations) >= 1
    print(f"\n  CA-05 Citas RAG ({len(citations)}): {'✓' if ca05_ok else '✗'}")
    for c in citations:
        print(f"    [{c.get('section','')}] {c.get('excerpt','')[:100]}")

    print(f"\n  Chunks recuperados ({len(chunks_ret)}):")
    for ch in chunks_ret:
        print(f"    dist={ch['distance']:.3f} | {ch['section']}")

    app_log = next((e for e in result["audit_log"] if e["node"] == "appetite_validation"), {})
    print(f"\n  Tokens appetite: {app_log.get('tokens_used',{}).get('total_tokens','?')}")

# Resumen CA-04
print(f"\n{'='*65}")
print(f"RESUMEN CA-04: {sum(ca04_results)}/{len(ca04_results)} veredictos correctos ({sum(ca04_results)/len(ca04_results):.0%})")
