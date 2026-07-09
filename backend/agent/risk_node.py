"""
Node 4 — Risk Assessment.
Puntúa el riesgo con LLM + RAG sobre pricing guidelines, detecta red flags
y activa HITL-3 si el score supera el umbral. Invoca el pricing stub con
tasas reales recuperadas de los guidelines.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm
from ..tools.rag_retriever import retrieve, format_context

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "risk_node.md"

RISK_SCORE_HITL_THRESHOLD = 75


def _build_pricing_query(state: AgentState) -> str:
    ext = state.get("extracted_data", {})
    parts = [
        state.get("line_of_business", ""),
        ext.get("activity_description", "") or "",
        ext.get("cnae_code", "") or "",
        "tasa base pricing",
    ]
    return " ".join(p for p in parts if p)


def _load_prompt(state: AgentState, rag_context: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    ext = state.get("extracted_data", {})
    loss = ext.get("loss_history")
    loss_str = str(loss) if loss is not None else "no informado"

    return (
        template
        .replace("{line_of_business}",    state.get("line_of_business", ""))
        .replace("{activity_description}", str(ext.get("activity_description") or "no informado"))
        .replace("{cnae_code}",           str(ext.get("cnae_code") or "no informado"))
        .replace("{province}",            str(ext.get("province") or "no informado"))
        .replace("{sum_insured_eur}",      str(ext.get("sum_insured_eur") or "no informado"))
        .replace("{requested_coverages}", str(ext.get("requested_coverages") or "no informado"))
        .replace("{loss_history}",        loss_str)
        .replace("{loss_ratio}",          str(ext.get("loss_ratio") or "no informado"))
        .replace("{renewal}",             str(ext.get("renewal")))
        .replace("{appetite_verdict}",    state.get("appetite_result", {}).get("verdict", "no disponible"))
        .replace("{rag_context}",         rag_context)
    )


def _parse_risk_json(content: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    return json.loads(json_str)


def risk_node(state: AgentState) -> AgentState:
    # Recuperar fragmentos de pricing guidelines relevantes
    query = _build_pricing_query(state)
    # Recuperar de pricing guidelines; si no hay suficientes chunks, ampliar sin filtro
    chunks = retrieve(query, n_results=4, source_filter="pricing_guidelines_property_casualty")
    if len(chunks) < 2:
        chunks = retrieve(query, n_results=4)
    rag_context = format_context(chunks)

    llm = get_llm(temperature=0.0)
    prompt = _load_prompt(state, rag_context)
    response = llm.invoke(prompt)
    content = response.content

    try:
        parsed = _parse_risk_json(content)
        risk_score       = int(parsed.get("risk_score", 50))
        risk_flags       = parsed.get("risk_flags", [])
        pricing_context  = parsed.get("pricing_context", {})
        scoring_reasoning = parsed.get("scoring_reasoning", "")
    except (json.JSONDecodeError, ValueError, TypeError):
        risk_score        = 50
        risk_flags        = [f"Error al parsear respuesta del LLM: {content[:150]}"]
        pricing_context   = {}
        scoring_reasoning = "error de parseo"

    # Invocar pricing stub con las tasas recuperadas del RAG
    pricing_output = _call_pricing_stub(state, risk_score, pricing_context)

    log_entry = {
        "node": "risk_assessment",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm+rag",
        "risk_score": risk_score,
        "risk_flags": risk_flags,
        "scoring_reasoning": scoring_reasoning,
        "rag_chunks_retrieved": len(chunks),
        "tokens_used": getattr(response, "usage_metadata", {}) or {},
    }
    return {
        **state,
        "risk_score":    risk_score,
        "risk_flags":    risk_flags,
        "pricing_output": pricing_output,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }


def route_after_risk(state: AgentState) -> str:
    """Arista condicional: riesgo elevado o flags → HITL-3, estándar → output."""
    if state.get("risk_score", 0) >= RISK_SCORE_HITL_THRESHOLD or _has_critical_flags(state):
        return "hitl_point_3"
    return "output_generation"


def _has_critical_flags(state: AgentState) -> bool:
    flags = state.get("risk_flags", [])
    critical_keywords = ["suma asegurada", "loss ratio", "siniestros", "concentración", "senior"]
    # Distinguir "dato alarmante presente" de "dato no informado": un flag que solo
    # señala la AUSENCIA del dato (p. ej. "Loss ratio no informado") no es crítico.
    absence_patterns = ["no informad", "pendiente de informaci", "sin informar",
                        "no se informa", "no consta"]
    for f in flags:
        fl = f.lower()
        if any(kw in fl for kw in critical_keywords):
            if not any(ap in fl for ap in absence_patterns):
                return True
    return False


def _call_pricing_stub(state: AgentState, risk_score: int, pricing_context: dict) -> dict:
    """
    Stub del motor de pricing de Chubb.
    Usa las tasas recuperadas del RAG en lugar de tasas fijas.
    En producción: reemplazar por llamada HTTP a pricing_tool_certified().
    """
    ext = state.get("extracted_data", {})
    sum_insured = ext.get("sum_insured_eur") or 0
    lob = state.get("line_of_business", "property")

    default_min = 0.8 if lob == "property" else 1.5
    default_max = 1.5 if lob == "property" else 2.5
    tasa_min = pricing_context.get("tasa_base_min_permil") or default_min
    tasa_max = pricing_context.get("tasa_base_max_permil") or default_max

    # Usar tasa media del rango, ajustada por risk_score (0-100 → factor 0.85-1.25)
    tasa_media = (tasa_min + tasa_max) / 2
    risk_factor = 0.85 + (risk_score / 100) * 0.40
    tasa_aplicada = round(tasa_media * risk_factor / 1000, 6)  # convertir ‰ → factor

    prima_tecnica = round(sum_insured * tasa_aplicada, 2)

    return {
        "source":            "pricing_stub_v2_rag_rates",
        "prima_tecnica_eur": prima_tecnica,
        "tasa_aplicada_permil": round(tasa_media * risk_factor, 4),
        "tasa_base_range":   f"{tasa_min}‰ – {tasa_max}‰",
        "risk_factor":       round(risk_factor, 3),
        "sum_insured_eur":   sum_insured,
        "coberturas":        ext.get("requested_coverages", []),
        "descuentos":        pricing_context.get("descuentos_aplicables", []),
        "recargos":          pricing_context.get("recargos_aplicables", []),
        "condicionado_adicional": pricing_context.get("condicionado_adicional", ""),
        "nota": "[STUB v2] Prima calculada con tasas RAG — reemplazar por pricing_tool_certified() en producción",
    }
