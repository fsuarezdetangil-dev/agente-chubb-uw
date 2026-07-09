"""
Pasada E2E completa sobre las 72 submissions sintéticas.
Mide CA-01 a CA-08 y guarda resultados en evals/results/.
Ejecutar desde la raíz: python scripts/run_e2e.py
"""

import sys, os, json, time, traceback, warnings, logging
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUNBUFFERED"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.getLogger("langsmith").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()
from observability.phoenix.init_tracing import init_tracing
init_tracing()

# Log file paralelo para cuando stdout está redirigido
_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "evals", "results", "e2e_progress.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
_log_fh = open(_LOG_PATH, "w", encoding="utf-8", buffering=1)

def _log(msg: str):
    _log_fh.write(msg + "\n")
    _log_fh.flush()
    try:
        print(msg, flush=True)
    except Exception:
        pass

from datetime import datetime, timezone
from pathlib import Path
from backend.agent.graph import get_default_graph
from backend.agent.state import AgentState

RESULTS_DIR = Path("evals/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

graph = get_default_graph()
# Solo campos extraíbles del email (sin cnae_code ni loss_history — DUDA-004)
CAMPOS_CRITICOS = ["company_name", "activity_description",
                   "province", "sum_insured_eur", "requested_coverages", "renewal"]


# ── helpers ──────────────────────────────────────────────────────────────────

def build_state(sub: dict) -> AgentState:
    broker = sub["broker"] if isinstance(sub.get("broker"), str) else sub.get("broker", {}).get("name", "")
    return {
        "submission_id":   sub["submission_id"],
        "submission_raw":  sub,
        "channel":         sub["channel"],
        "line_of_business": sub["line_of_business"],
        "metadata":        {"broker_name": broker},
        "extracted_data":  {},
        "missing_fields":  [],
        "appetite_result": {},
        "risk_score":      0,
        "risk_flags":      [],
        "pricing_output":  {},
        "outputs":         {},
        "audit_log":       [],
        "hitl_status":     "none",
        "hitl_point":      "none",
        "plan_json":       [],
    }


def resume_all_hitl(result, config, sub, max_hitl=3):
    snapshot = graph.get_state(config)
    count = 0
    hitl_nodes_triggered = []
    # Capturar missing_fields ANTES del primer resume (para CA-03)
    missing_fields_pre_hitl = list(result.get("missing_fields", []))
    while snapshot.next and count < max_hitl:
        node = snapshot.next[0]
        hitl_nodes_triggered.append(node)
        updates = {"hitl_status": "approved"}
        if node == "hitl_point_1":
            updates["extracted_data"] = sub["extracted_data_ground_truth"]
            updates["missing_fields"] = []
        graph.update_state(config, updates)
        result = graph.invoke(None, config=config)
        snapshot = graph.get_state(config)
        count += 1
    return result, hitl_nodes_triggered, missing_fields_pre_hitl


def eval_ca01(result, sub):
    return result.get("line_of_business") == sub["line_of_business"]


def eval_ca02(result, sub):
    gt = sub.get("extracted_data_ground_truth", {})
    ext = result.get("extracted_data", {})
    hits, total = 0, 0
    for c in CAMPOS_CRITICOS:
        gt_val = gt.get(c)
        if gt_val is None:
            continue
        total += 1
        ex_val = ext.get(c)
        if isinstance(gt_val, list) and gt_val and isinstance(gt_val[0], dict):
            ok = len(gt_val) == len(ex_val or [])
        elif isinstance(gt_val, list):
            ok = set(str(x).lower() for x in gt_val) == set(str(x).lower() for x in (ex_val or []))
        else:
            ok = str(gt_val).lower().strip() == str(ex_val).lower().strip()
        hits += int(ok)
    return hits / total if total else None


def eval_ca03(result, sub, missing_pre_hitl=None):
    """Evalúa con missing_fields capturados ANTES del resume de HITL-1
    (el resume los limpia con ground truth, así que el estado final no es útil)."""
    gt_missing = set(sub.get("missing_fields_expected", []))
    # Filtrar gt_missing a solo campos EMAIL (cnae/loss_history no activan HITL-1 en v2)
    from backend.agent.extraction_node import CAMPOS_EMAIL
    gt_missing_email = gt_missing & CAMPOS_EMAIL
    detected = set(missing_pre_hitl) if missing_pre_hitl is not None else set(result.get("missing_fields", []))
    if not gt_missing_email:
        return len(detected) == 0
    return gt_missing_email.issubset(detected)


def eval_ca04(result, sub):
    verdict_map = {"dentro": "dentro", "fuera": "fuera", "revision": "revision"}
    expected = verdict_map.get(sub.get("appetite_expected", ""), "")
    actual   = result.get("appetite_result", {}).get("verdict", "")
    return actual == expected


def eval_ca05(result):
    cits = result.get("appetite_result", {}).get("rag_citations", [])
    return len(cits) >= 1


def eval_ca06(result, sub, hitl_triggered):
    expected = sub.get("expected_hitl_trigger", "")
    if expected == "STP_dentro_apetito":
        return len(hitl_triggered) == 0
    elif expected == "HITL-1_datos_incompletos":
        return "hitl_point_1" in hitl_triggered
    elif expected == "HITL-2_declinar":
        return "hitl_point_2" in hitl_triggered
    elif expected == "HITL-3_referir_senior":
        return "hitl_point_3" in hitl_triggered
    return True


def eval_ca07(result):
    score = result.get("outputs", {}).get("_quality", {}).get("llm_judge_score", 0)
    return score >= 85, score


def eval_ca08(result):
    log = result.get("audit_log", [])
    if len(log) < 2:
        return None, None
    t0 = datetime.fromisoformat(log[0]["timestamp"])
    t1 = datetime.fromisoformat(log[-1]["timestamp"])
    elapsed = (t1 - t0).total_seconds()
    return elapsed < 240, round(elapsed, 1)


# ── main loop ─────────────────────────────────────────────────────────────────

with open("data/samples/submissions_synthetic_all_70.json", encoding="utf-8") as f:
    subs = json.load(f)

# Añadir edge cases
with open("data/samples/submissions_edge_cases_12.json", encoding="utf-8") as f:
    edges = json.load(f)

# Unir y deduplicar
seen = {s["submission_id"] for s in subs}
for e in edges:
    if e["submission_id"] not in seen:
        subs.append(e)

_log(f"Submissions a procesar: {len(subs)}")
_log(f"Inicio: {datetime.now().strftime('%H:%M:%S')}\n")

records = []
errors  = []

for i, sub in enumerate(subs):
    sid = sub["submission_id"]
    tag = sub.get("scenario_tag", "")
    prefix = f"[{i+1:02d}/{len(subs)}] {sid} | {tag}"

    try:
        t_start = time.time()
        config = {"configurable": {"thread_id": sid + "-e2e"}}
        result = graph.invoke(build_state(sub), config=config)
        result, hitl_triggered, missing_pre_hitl = resume_all_hitl(result, config, sub)
        elapsed_wall = round(time.time() - t_start, 1)

        ca01 = eval_ca01(result, sub)
        ca02 = eval_ca02(result, sub)
        ca03 = eval_ca03(result, sub, missing_pre_hitl)
        ca04 = eval_ca04(result, sub)
        ca05 = eval_ca05(result)
        ca06 = eval_ca06(result, sub, hitl_triggered)
        ca07_ok, ca07_score = eval_ca07(result)
        ca08_ok, ca08_secs  = eval_ca08(result)

        record = {
            "submission_id":   sid,
            "scenario_tag":    tag,
            "line_of_business": sub["line_of_business"],
            "expected_hitl":   sub.get("expected_hitl_trigger", ""),
            "hitl_triggered":  hitl_triggered,
            "missing_pre_hitl": missing_pre_hitl,
            "ca01_lob":        ca01,
            "ca02_extraction": ca02,
            "ca03_missing":    ca03,
            "ca04_appetite":   ca04,
            "ca05_rag_cits":   ca05,
            "ca06_hitl":       ca06,
            "ca07_score":      ca07_score,
            "ca07_ok":         ca07_ok,
            "ca08_secs":       ca08_secs,
            "ca08_ok":         ca08_ok,
            "appetite_verdict": result.get("appetite_result", {}).get("verdict", ""),
            "risk_score":      result.get("risk_score", 0),
            "prima_eur":       result.get("pricing_output", {}).get("prima_tecnica_eur", 0),
            "wall_secs":       elapsed_wall,
            "error":           None,
        }
        records.append(record)

        # Indicador compacto por línea
        checks = "".join([
            "✓" if ca01 else "✗",
            "✓" if ca02 and ca02 >= 0.8 else ("~" if ca02 and ca02 >= 0.5 else "✗"),
            "✓" if ca03 else "✗",
            "✓" if ca04 else "✗",
            "✓" if ca05 else "✗",
            "✓" if ca06 else "✗",
            "✓" if ca07_ok else "✗",
            "✓" if ca08_ok else "✗",
        ])
        _log(f"{prefix} | [{checks}] {elapsed_wall}s | risk={result.get('risk_score',0)} | prima={result.get('pricing_output',{}).get('prima_tecnica_eur',0):.0f}EUR")

    except Exception as exc:
        elapsed_wall = round(time.time() - t_start, 1)
        err_msg = str(exc)[:200].encode("ascii", errors="replace").decode("ascii")
        _log(f"{prefix} | ERROR: {err_msg}")
        errors.append({"submission_id": sid, "error": err_msg, "traceback": traceback.format_exc()[-500:]})
        records.append({
            "submission_id": sid, "scenario_tag": tag,
            "line_of_business": sub["line_of_business"],
            "expected_hitl": sub.get("expected_hitl_trigger", ""),
            "hitl_triggered": [], "ca01_lob": None, "ca02_extraction": None,
            "ca03_missing": None, "ca04_appetite": None, "ca05_rag_cits": None,
            "ca06_hitl": None, "ca07_score": 0, "ca07_ok": False,
            "ca08_secs": None, "ca08_ok": None, "appetite_verdict": "",
            "risk_score": 0, "prima_eur": 0, "wall_secs": elapsed_wall, "error": err_msg,
        })


# ── resumen de métricas ───────────────────────────────────────────────────────

ok = [r for r in records if r["error"] is None]
n  = len(ok)

def pct(vals):
    v = [x for x in vals if x is not None]
    return f"{sum(v)}/{len(v)} = {sum(v)/len(v):.0%}" if v else "n/a"

def avg(vals):
    v = [x for x in vals if x is not None]
    return f"{sum(v)/len(v):.2f}" if v else "n/a"

_log(f"\n{'='*65}")
_log(f"RESULTADOS E2E -- {n}/{len(records)} submissions completadas sin error")
_log(f"{'='*65}")
_log(f"CA-01 LOB accuracy:           {pct([r['ca01_lob'] for r in ok])}")
_log(f"CA-02 Extraction avg accuracy: {avg([r['ca02_extraction'] for r in ok])}")
_log(f"CA-03 Missing fields detect:   {pct([r['ca03_missing'] for r in ok])}")
_log(f"CA-04 Appetite verdict:        {pct([r['ca04_appetite'] for r in ok])}")
_log(f"CA-05 RAG citations:           {pct([r['ca05_rag_cits'] for r in ok])}")
_log(f"CA-06 HITL correcto:           {pct([r['ca06_hitl'] for r in ok])}")
_log(f"CA-07 LLM-Judge >=85:          {pct([r['ca07_ok'] for r in ok])} | avg score: {avg([r['ca07_score'] for r in ok])}")
_log(f"CA-08 Time-to-quote <4min:     {pct([r['ca08_ok'] for r in ok])} | avg: {avg([r['ca08_secs'] for r in ok])}s")
_log(f"\nErrores: {len(errors)}")
if errors:
    for e in errors:
        _log(f"  {e['submission_id']}: {e['error']}")

# Distribución de veredictos de apetito
from collections import Counter
verdicts = Counter(r["appetite_verdict"] for r in ok)
hitl_dist = Counter(r["expected_hitl"] for r in ok)
_log(f"\nDistribucion veredictos apetito: {dict(verdicts)}")
_log(f"Distribucion HITL esperado:      {dict(hitl_dist)}")

# Guardar resultados
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path = RESULTS_DIR / f"e2e_{ts}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"records": records, "errors": errors,
               "timestamp": ts, "n_submissions": len(records)}, f, ensure_ascii=False, indent=2)
_log(f"\nResultados guardados en: {out_path}")
_log_fh.close()
