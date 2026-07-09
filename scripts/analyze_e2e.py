"""Análisis de resultados del E2E — fallos por criterio."""
import json, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

results_dir = Path("evals/results")
latest = sorted(results_dir.glob("e2e_*.json"))[-1]
print(f"Leyendo: {latest}\n")

with open(latest, encoding="utf-8") as f:
    data = json.load(f)

records = data["records"]
ok = [r for r in records if r["error"] is None]

# ── resumen global ──
print("=" * 65)
print(f"RESUMEN — {len(ok)}/{len(records)} sin error")
print("=" * 65)

def pct(vals):
    v = [x for x in vals if x is not None]
    if not v: return "n/a"
    return f"{sum(v)}/{len(v)} = {sum(v)/len(v):.0%}"

def avg(vals):
    v = [x for x in vals if x is not None]
    return f"{sum(v)/len(v):.2f}" if v else "n/a"

print(f"CA-01 LOB accuracy:            {pct([r['ca01_lob'] for r in ok])}")
print(f"CA-02 Extraction avg:          {avg([r['ca02_extraction'] for r in ok])}")
print(f"CA-03 Missing fields:          {pct([r['ca03_missing'] for r in ok])}")
print(f"CA-04 Appetite verdict:        {pct([r['ca04_appetite'] for r in ok])}")
print(f"CA-05 RAG citations:           {pct([r['ca05_rag_cits'] for r in ok])}")
print(f"CA-06 HITL routing:            {pct([r['ca06_hitl'] for r in ok])}")
print(f"CA-07 LLM-Judge >=85:          {pct([r['ca07_ok'] for r in ok])} | avg={avg([r['ca07_score'] for r in ok])}")
print(f"CA-08 Time-to-quote <4min:     {pct([r['ca08_ok'] for r in ok])} | avg={avg([r['ca08_secs'] for r in ok])}s")

# ── CA-01 fallos ──
ca01_fail = [r for r in ok if not r["ca01_lob"]]
print(f"\n=== CA-01 FALLOS ({len(ca01_fail)}) — LOB incorrecta ===")
for r in ca01_fail:
    sid = r["submission_id"]
    tag = r["scenario_tag"]
    lob = r["line_of_business"]
    print(f"  {sid} | {tag} | expected_lob={lob}")

# ── CA-04 fallos ──
ca04_fail = [r for r in ok if not r["ca04_appetite"]]
print(f"\n=== CA-04 FALLOS ({len(ca04_fail)}) — apetito incorrecto ===")
for r in ca04_fail:
    sid = r["submission_id"]
    tag = r["scenario_tag"]
    verdict = r["appetite_verdict"]
    expected = r["expected_hitl"]
    print(f"  {sid} | {tag} | verdict={verdict} | expected_hitl={expected}")

# ── CA-06 fallos ──
ca06_fail = [r for r in ok if not r["ca06_hitl"]]
print(f"\n=== CA-06 FALLOS ({len(ca06_fail)}) — HITL routing incorrecto ===")
for r in ca06_fail:
    sid = r["submission_id"]
    tag = r["scenario_tag"]
    exp = r["expected_hitl"]
    trig = r["hitl_triggered"]
    verdict = r["appetite_verdict"]
    print(f"  {sid} | {tag} | expected={exp} | triggered={trig} | appetite={verdict}")

# ── CA-03 fallos ──
ca03_fail = [r for r in ok if not r["ca03_missing"]]
print(f"\n=== CA-03 FALLOS ({len(ca03_fail)}) — missing fields no detectados ===")
for r in ca03_fail:
    sid = r["submission_id"]
    tag = r["scenario_tag"]
    print(f"  {sid} | {tag}")

# ── Prima = 0 en casos no-incompleto/fuera ──
prima0 = [r for r in ok if r["prima_eur"] == 0
          and "incompleto" not in r["scenario_tag"]
          and r["appetite_verdict"] not in ("fuera",)]
print(f"\n=== PRIMA=0 inesperado ({len(prima0)}) ===")
for r in prima0:
    sid = r["submission_id"]
    tag = r["scenario_tag"]
    verdict = r["appetite_verdict"]
    risk = r["risk_score"]
    print(f"  {sid} | {tag} | verdict={verdict} | risk={risk}")
