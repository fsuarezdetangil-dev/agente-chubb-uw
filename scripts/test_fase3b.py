"""
Test de Fase 3B: Data Extraction Node con LLM real.
Prueba tres escenarios: STP completo, incompleto (HITL-1) y edge case.
Ejecutar desde la raíz: python scripts/test_fase3b.py
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
    return {
        "submission_id": sub["submission_id"],
        "submission_raw": sub,
        "channel": sub["channel"],
        "line_of_business": sub["line_of_business"],
        "metadata": {
            "broker_name": sub["broker"] if isinstance(sub.get("broker"), str) else sub.get("broker", {}).get("name", ""),
            "tomador": sub.get("extracted_data_ground_truth", {}).get("company_name", ""),
        },
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


def evaluate_extraction(result: dict, sub: dict) -> dict:
    """Compara extracted_data con ground-truth campo a campo."""
    gt = sub.get("extracted_data_ground_truth", {})
    extracted = result.get("extracted_data", {})
    campos = ["company_name", "cnae_code", "activity_description", "province",
              "sum_insured_eur", "requested_coverages", "loss_history", "renewal"]
    hits, total = 0, 0
    detalles = []
    for c in campos:
        gt_val = gt.get(c)
        ex_val = extracted.get(c)
        if gt_val is None:
            continue
        total += 1
        if isinstance(gt_val, list) and gt_val and isinstance(gt_val[0], dict):
            # Para listas de dicts (loss_history): comparar longitud como proxy
            ok = len(gt_val) == len(ex_val or [])
        elif isinstance(gt_val, list):
            ok = set(str(x).lower() for x in gt_val) == set(str(x).lower() for x in (ex_val or []))
        else:
            ok = str(gt_val).lower().strip() == str(ex_val).lower().strip()
        hits += int(ok)
        detalles.append(f"  {'✓' if ok else '✗'} {c}: extraído={ex_val!r} | gt={gt_val!r}")
    return {"hits": hits, "total": total, "accuracy": hits/total if total else 0, "detalles": detalles}


# Cargar datasets
with open("data/samples/submissions_property_30.json", encoding="utf-8") as f:
    prop = json.load(f)
with open("data/samples/submissions_casualty_30.json", encoding="utf-8") as f:
    cas = json.load(f)

escenarios = [
    ("STP property completa",    next(s for s in prop if s["expected_hitl_trigger"] == "STP_dentro_apetito")),
    ("HITL-1 incompleta",        next(s for s in prop if s["expected_hitl_trigger"] == "HITL-1_datos_incompletos")),
    ("STP casualty completa",    next(s for s in cas  if s["expected_hitl_trigger"] == "STP_dentro_apetito")),
]

for nombre, sub in escenarios:
    print(f"\n{'='*60}")
    print(f"ESCENARIO: {nombre} | {sub['submission_id']} | {sub['scenario_tag']}")
    print(f"{'='*60}")

    config = {"configurable": {"thread_id": sub["submission_id"] + "-3B"}}
    result = graph.invoke(build_state(sub), config=config)

    # Buscar log de extraction
    ext_log = next((e for e in result["audit_log"] if e["node"] == "data_extraction"), {})

    print(f"Campos extraídos ({len(ext_log.get('fields_extracted',[]))}): {ext_log.get('fields_extracted')}")
    print(f"Missing fields:   {result['missing_fields']} (esperado: {sub['missing_fields_expected']})")
    print(f"Confianza:        {ext_log.get('extraction_confidence')}")
    print(f"Notas:            {ext_log.get('extraction_notes','')[:120]}")
    print(f"HITL activado:    {result['hitl_status']} (esperado: {'HITL-1' if sub['missing_fields_expected'] else 'none'})")

    eval_result = evaluate_extraction(result, sub)
    print(f"\nCA-02 Accuracy:   {eval_result['hits']}/{eval_result['total']} = {eval_result['accuracy']:.0%}")
    for d in eval_result["detalles"]:
        print(d)

    # CA-03: detección de campos faltantes
    gt_missing = set(sub["missing_fields_expected"])
    detected_missing = set(result["missing_fields"])
    ca03_ok = gt_missing.issubset(detected_missing)
    print(f"\nCA-03 Missing fields detectados correctamente: {'✓' if ca03_ok else '✗'}")
    if gt_missing:
        print(f"  Esperados: {gt_missing} | Detectados: {detected_missing}")

    tokens = ext_log.get("tokens_used", {})
    print(f"\nTokens extraction: {tokens.get('total_tokens','?')}")
