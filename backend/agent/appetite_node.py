"""
Node 3 — Appetite & Validation.
Recupera fragmentos relevantes de los guidelines via RAG y usa el LLM para emitir
el veredicto de apetito con citas obligatorias.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm
from ..tools.rag_retriever import retrieve, format_context

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "appetite_node.md"


def _build_rag_query(state: AgentState) -> str:
    """Construye la query de retrieval combinando actividad + línea + coberturas."""
    ext = state.get("extracted_data", {})
    parts = [
        state.get("line_of_business", ""),
        ext.get("activity_description", ""),
        ext.get("cnae_code", "") or "",
        ", ".join(ext.get("requested_coverages", []) or []),
    ]
    return " ".join(p for p in parts if p).strip()


def _load_prompt(state: AgentState, rag_context: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    ext = state.get("extracted_data", {})
    loss = ext.get("loss_history")
    loss_str = str(loss) if loss is not None else "no informado"

    return (
        template
        .replace("{line_of_business}", state.get("line_of_business", ""))
        .replace("{activity_description}", str(ext.get("activity_description") or "no informado"))
        .replace("{cnae_code}", str(ext.get("cnae_code") or "no informado"))
        .replace("{province}", str(ext.get("province") or "no informado"))
        .replace("{sum_insured_eur}", str(ext.get("sum_insured_eur") or "no informado"))
        .replace("{requested_coverages}", str(ext.get("requested_coverages") or "no informado"))
        .replace("{loss_history}", loss_str)
        .replace("{renewal}", str(ext.get("renewal")))
        .replace("{rag_context}", rag_context)
    )


def _parse_appetite_json(content: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    return json.loads(json_str)


def appetite_node(state: AgentState) -> AgentState:
    # Recuperar fragmentos relevantes de los guidelines de apetito
    query = _build_rag_query(state)
    chunks = retrieve(
        query,
        n_results=5,
        source_filter="appetite_guidelines_property_casualty",
    )
    rag_context = format_context(chunks)

    llm = get_llm(temperature=0.0)
    prompt = _load_prompt(state, rag_context)
    response = llm.invoke(prompt)
    content = response.content

    try:
        parsed = _parse_appetite_json(content)
        verdict     = parsed.get("verdict", "revision")
        confidence  = parsed.get("confidence", "low")
        justification = parsed.get("justification", "")
        citations   = parsed.get("rag_citations", [])
        limitations = parsed.get("data_limitations", "")
    except (json.JSONDecodeError, ValueError):
        verdict     = "revision"
        confidence  = "low"
        justification = f"Error al parsear respuesta del LLM: {content[:200]}"
        citations   = []
        limitations = "error de parseo"

    appetite_result = {
        "verdict":       verdict,
        "confidence":    confidence,
        "justification": justification,
        "rag_citations": citations,
        "data_limitations": limitations,
        "retrieved_chunks": [
            {"section": c["section_title"], "distance": c["distance"]}
            for c in chunks
        ],
    }

    log_entry = {
        "node": "appetite_validation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm+rag",
        "verdict": verdict,
        "confidence": confidence,
        "rag_chunks_retrieved": len(chunks),
        "tokens_used": getattr(response, "usage_metadata", {}) or {},
    }
    return {
        **state,
        "appetite_result": appetite_result,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }


def route_after_appetite(state: AgentState) -> str:
    """Arista condicional: fuera o revision → HITL-2, dentro → risk_assessment."""
    verdict = state.get("appetite_result", {}).get("verdict", "dentro")
    if verdict in ("fuera", "revision"):
        return "hitl_point_2"
    return "risk_assessment"
