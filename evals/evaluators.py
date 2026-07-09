"""
Evaluadores CA-01 a CA-08 para el agente UW de Chubb EMEA.

Cada evaluador tiene firma compatible con LangSmith:
    evaluator(run: Run, example: Example) -> EvaluationResult

También exporta versiones standalone para uso en scripts locales:
    eval_ca0X(result: dict, reference: dict) -> bool | float | None

Criterios de aceptación:
    CA-01  LOB accuracy         ≥ 95 %
    CA-02  Extraction accuracy  ≥ 80 % de campos críticos
    CA-03  Missing-fields detection  ≥ 90 %
    CA-04  Appetite verdict     ≥ 85 %
    CA-05  RAG citations presentes  100 %
    CA-06  HITL routing correcto    ≥ 95 %
    CA-07  LLM-Judge score      ≥ 85/100 en ≥ 90 % de submissions
    CA-08  Time-to-quote        < 4 min en ≥ 95 %
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Campos evaluados en CA-02: solo los extraíbles del email body.
# cnae_code y loss_history se excluyen porque vienen de adjuntos (DUDA-004, sin pdf_parser).
CAMPOS_CRITICOS = [
    "company_name", "activity_description",
    "province", "sum_insured_eur", "requested_coverages", "renewal",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_output(run_or_result) -> dict:
    """Extrae el dict de outputs tanto de un Run de LangSmith como de un dict directo."""
    if hasattr(run_or_result, "outputs"):          # LangSmith Run object
        return run_or_result.outputs or {}
    return run_or_result or {}                      # dict directo (uso local)


def _get_reference(example_or_ref) -> dict:
    """Extrae el dict de referencia tanto de un Example de LangSmith como de un dict directo."""
    if hasattr(example_or_ref, "outputs"):         # LangSmith Example object
        return example_or_ref.outputs or {}
    return example_or_ref or {}                    # dict directo (uso local)


# ── evaluadores locales (standalone) ─────────────────────────────────────────

def eval_ca01(result: dict, reference: dict) -> bool:
    """CA-01: LOB clasificada correctamente."""
    return result.get("line_of_business") == reference.get("line_of_business")


def eval_ca02(result: dict, reference: dict) -> float | None:
    """CA-02: Fracción de campos críticos extraídos correctamente (0.0–1.0)."""
    gt = reference.get("extracted_data_ground_truth", {})
    ext = result.get("extracted_data", {})
    hits, total = 0, 0
    for campo in CAMPOS_CRITICOS:
        gt_val = gt.get(campo)
        if gt_val is None:
            continue
        total += 1
        ex_val = ext.get(campo)
        if isinstance(gt_val, list) and gt_val and isinstance(gt_val[0], dict):
            ok = len(gt_val) == len(ex_val or [])
        elif isinstance(gt_val, list):
            ok = set(str(x).lower() for x in gt_val) == set(str(x).lower() for x in (ex_val or []))
        else:
            ok = str(gt_val).lower().strip() == str(ex_val).lower().strip()
        hits += int(ok)
    return hits / total if total else None


def eval_ca03(result: dict, reference: dict) -> bool:
    """CA-03: Campos faltantes detectados correctamente.

    Lee missing_fields_at_extraction (lo que Node 2 detectó en extracción) si
    está presente; si no, cae al missing_fields final. Necesario porque el
    resume de HITL-1 vacía missing_fields al inyectar el ground truth, lo que
    antes hacía que CA-03 midiera un estado posterior a la resolución del HITL.
    El fallback preserva la comparación con pasadas anteriores (sin el campo)."""
    gt_missing = set(reference.get("missing_fields_expected", []))
    if result.get("missing_fields_at_extraction") is not None:
        detected = set(result.get("missing_fields_at_extraction") or [])
    else:
        detected = set(result.get("missing_fields", []))
    if not gt_missing:
        return len(detected) == 0
    return gt_missing.issubset(detected)


def eval_ca04(result: dict, reference: dict) -> bool:
    """CA-04: Veredicto de apetito correcto."""
    expected = reference.get("appetite_expected", "")
    actual   = result.get("appetite_result", {}).get("verdict", "")
    return actual == expected


def eval_ca05(result: dict, _reference: dict | None = None) -> bool:
    """CA-05: Al menos una cita RAG en el resultado de apetito."""
    cits = result.get("appetite_result", {}).get("rag_citations", [])
    return len(cits) >= 1


def eval_ca06(result: dict, reference: dict, hitl_triggered: list[str] | None = None) -> bool:
    """CA-06: El punto HITL correcto fue activado (o STP sin HITL)."""
    expected = reference.get("expected_hitl_trigger", "")
    triggered = hitl_triggered or result.get("_hitl_triggered", [])
    if expected == "STP_dentro_apetito":
        return len(triggered) == 0
    elif expected == "HITL-1_datos_incompletos":
        return "hitl_point_1" in triggered
    elif expected == "HITL-2_declinar":
        return "hitl_point_2" in triggered
    elif expected == "HITL-3_referir_senior":
        return "hitl_point_3" in triggered
    return True


def eval_ca07(result: dict, _reference: dict | None = None) -> tuple[bool, int]:
    """CA-07: LLM-Judge score >= 85/100. Devuelve (ok, score)."""
    score = result.get("outputs", {}).get("_quality", {}).get("llm_judge_score", 0)
    return score >= 85, score


def eval_ca08(result: dict, _reference: dict | None = None) -> tuple[bool | None, float | None]:
    """CA-08: Time-to-quote < 4 min. Devuelve (ok, segundos)."""
    log = result.get("audit_log", [])
    if len(log) < 2:
        return None, None
    t0 = datetime.fromisoformat(log[0]["timestamp"])
    t1 = datetime.fromisoformat(log[-1]["timestamp"])
    elapsed = (t1 - t0).total_seconds()
    return elapsed < 240, round(elapsed, 1)


# ── evaluadores LangSmith (firma Run, Example → EvaluationResult) ─────────────

def _make_result(key: str, score: float | None, comment: str = "") -> dict:
    """Crea un EvaluationResult compatible con LangSmith."""
    return {"key": key, "score": score, "comment": comment}


def langsmith_ca01(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca01(result, reference)
    return _make_result("ca01_lob_accuracy", float(ok),
                        f"got={result.get('line_of_business')} expected={reference.get('line_of_business')}")


def langsmith_ca02(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    score = eval_ca02(result, reference)
    return _make_result("ca02_extraction_accuracy", score,
                        f"fraccion_campos_criticos={score:.2f}" if score is not None else "sin gt")


def langsmith_ca03(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca03(result, reference)
    detected  = result.get("missing_fields_at_extraction")
    if detected is None:
        detected = result.get("missing_fields", [])
    expected  = reference.get("missing_fields_expected", [])
    return _make_result("ca03_missing_fields", float(ok),
                        f"detected={detected} expected={expected}")


def langsmith_ca04(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca04(result, reference)
    return _make_result("ca04_appetite_verdict", float(ok),
                        f"got={result.get('appetite_result',{}).get('verdict')} expected={reference.get('appetite_expected')}")


def langsmith_ca05(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok = eval_ca05(result)
    n_cits = len(result.get("appetite_result", {}).get("rag_citations", []))
    return _make_result("ca05_rag_citations", float(ok), f"n_citations={n_cits}")


def langsmith_ca06(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca06(result, reference)
    return _make_result("ca06_hitl_routing", float(ok),
                        f"expected={reference.get('expected_hitl_trigger')}")


def langsmith_ca07(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok, score = eval_ca07(result)
    return _make_result("ca07_llm_judge", float(ok), f"score={score}/100")


def langsmith_ca08(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok, secs = eval_ca08(result)
    if ok is None:
        return _make_result("ca08_time_to_quote", None, "audit_log insuficiente")
    return _make_result("ca08_time_to_quote", float(ok), f"{secs}s")


ALL_EVALUATORS = [
    langsmith_ca01, langsmith_ca02, langsmith_ca03, langsmith_ca04,
    langsmith_ca05, langsmith_ca06, langsmith_ca07, langsmith_ca08,
]
