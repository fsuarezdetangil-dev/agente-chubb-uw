"""Inspecciona ground truth de submissions incompleto para ajustar missing_fields_expected."""
import json, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.agent.extraction_node import CAMPOS_EMAIL, CAMPOS_ADJUNTO

files = [
    "data/samples/submissions_synthetic_all_70.json",
    "data/samples/submissions_edge_cases_12.json",
]
subs = []
for f in files:
    with open(f, encoding="utf-8") as fh:
        subs += json.load(fh)

incompleto = [s for s in subs if "incompleto" in s.get("scenario_tag", "")]
print(f"Submissions incompleto: {len(incompleto)}\n")
print(f"CAMPOS_EMAIL (activan HITL-1): {CAMPOS_EMAIL}")
print(f"CAMPOS_ADJUNTO (no activan HITL-1): {CAMPOS_ADJUNTO}\n")

for s in incompleto:
    sid = s["submission_id"]
    tag = s["scenario_tag"]
    mf = s.get("missing_fields_expected", [])
    gt = s.get("extracted_data_ground_truth", {})

    # Separar los campos missing en email vs adjunto
    mf_email = [f for f in mf if f in CAMPOS_EMAIL]
    mf_adjunto = [f for f in mf if f in CAMPOS_ADJUNTO]
    mf_other = [f for f in mf if f not in CAMPOS_EMAIL and f not in CAMPOS_ADJUNTO]

    # Campos de email que SÍ tienen valor en gt (el LLM debería poder extraerlos)
    email_con_valor = {k: v for k, v in gt.items() if k in CAMPOS_EMAIL and v is not None and v != "" and v != []}

    print(f"{sid} | {tag}")
    print(f"  missing_expected actual:  {mf}")
    print(f"    -> email fields missing: {mf_email}")
    print(f"    -> adjunto fields missing: {mf_adjunto}")
    print(f"    -> otros: {mf_other}")
    print(f"  email fields con valor en gt: {list(email_con_valor.keys())}")
    # Sugerencia: solo deberían quedar en missing los campos de email que son null en gt
    mf_email_reales = [f for f in CAMPOS_EMAIL if gt.get(f) is None or gt.get(f) == "" or (isinstance(gt.get(f), list) and len(gt.get(f)) == 0)]
    print(f"  -> missing_fields_expected CORREGIDO (solo email nullos en gt): {mf_email_reales}")
    print()
