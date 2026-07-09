"""
Actualiza missing_fields_expected en los datos sintéticos para reflejar
la arquitectura real del PoC: solo los campos de EMAIL pueden activar HITL-1.
Los campos de adjunto (cnae_code, loss_history) se retiran del expected
porque el PoC no tiene pdf_parser (DUDA-004).
"""
import json, sys, os, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.agent.extraction_node import CAMPOS_EMAIL, CAMPOS_ADJUNTO

DATA_FILES = [
    "data/samples/submissions_synthetic_all_70.json",
    "data/samples/submissions_edge_cases_12.json",
]

for path in DATA_FILES:
    with open(path, encoding="utf-8") as f:
        subs = json.load(f)

    # Hacer backup
    backup = path.replace(".json", "_bak.json")
    shutil.copy(path, backup)

    changed = 0
    for sub in subs:
        old_mf = sub.get("missing_fields_expected", [])
        # Quedarse solo con campos de EMAIL que son realmente null en el gt
        gt = sub.get("extracted_data_ground_truth", {})
        new_mf = [
            f for f in old_mf
            if f in CAMPOS_EMAIL  # solo email fields
            # y además son null/vacíos en el gt (confirma que realmente faltan)
            and (gt.get(f) is None or gt.get(f) == "" or (isinstance(gt.get(f), list) and len(gt.get(f)) == 0))
        ]
        if sorted(old_mf) != sorted(new_mf):
            sid = sub["submission_id"]
            tag = sub.get("scenario_tag", "")
            print(f"  {sid} | {tag}")
            print(f"    antes:  {sorted(old_mf)}")
            print(f"    despues: {sorted(new_mf)}")
            sub["missing_fields_expected"] = new_mf
            changed += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)

    print(f"\n{path}: {changed} submissions actualizadas (backup en {backup})\n")

print("GT actualizado correctamente.")
