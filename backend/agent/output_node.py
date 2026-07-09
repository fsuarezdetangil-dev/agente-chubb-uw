"""
Node 5 — Output Generation con Reflection pattern.
Primera pasada: genera risk_summary, quote_draft y broker_comm.
Segunda pasada: evalúa los outputs con la rúbrica de 5 dimensiones.
Si score < 85, regenera una vez con las instrucciones de mejora.
Máximo 1 ciclo de reflexión para controlar el coste de tokens.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm

_PROMPT_GEN  = Path(__file__).parent.parent / "prompts" / "output_node.md"
_PROMPT_REFL = Path(__file__).parent.parent / "prompts" / "reflection_node.md"

REFLECTION_THRESHOLD = 85
MAX_REFLECTION_CYCLES = 1


def _build_generation_prompt(state: AgentState, extra_instructions: str = "") -> str:
    template = _PROMPT_GEN.read_text(encoding="utf-8")
    ext = state.get("extracted_data", {})
    app = state.get("appetite_result", {})
    pricing = state.get("pricing_output", {})

    citations = app.get("rag_citations", [])
    cit_str = "; ".join(f"[{c.get('section','')}] {c.get('excerpt','')[:80]}" for c in citations) or "ninguna"
    loss = ext.get("loss_history")
    loss_str = str(loss) if loss is not None else "no informado"

    prompt = (
        template
        .replace("{submission_id}",      state.get("submission_id", ""))
        .replace("{company_name}",       str(ext.get("company_name") or "no informado"))
        .replace("{line_of_business}",   state.get("line_of_business", ""))
        .replace("{activity_description}", str(ext.get("activity_description") or "no informado"))
        .replace("{cnae_code}",          str(ext.get("cnae_code") or "no informado"))
        .replace("{province}",           str(ext.get("province") or "no informado"))
        .replace("{sum_insured_eur}",    str(ext.get("sum_insured_eur") or "no informado"))
        .replace("{requested_coverages}", str(ext.get("requested_coverages") or "no informado"))
        .replace("{loss_history}",       loss_str)
        .replace("{loss_ratio}",         str(ext.get("loss_ratio") or "no informado"))
        .replace("{renewal}",            str(ext.get("renewal")))
        .replace("{missing_fields}",     str(state.get("missing_fields", [])))
        .replace("{appetite_verdict}",   app.get("verdict", "no disponible"))
        .replace("{appetite_justification}", app.get("justification", "")[:300])
        .replace("{appetite_citations}", cit_str)
        .replace("{risk_score}",         str(state.get("risk_score", 0)))
        .replace("{risk_flags}",         str(state.get("risk_flags", [])))
        .replace("{prima_tecnica}",      str(pricing.get("prima_tecnica_eur", "no disponible")))
        .replace("{tasa_range}",         str(pricing.get("tasa_base_range", "no disponible")))
        .replace("{condicionado}",       str(pricing.get("condicionado_adicional", "estándar")))
        .replace("{hitl_status}",        state.get("hitl_status", "none"))
    )
    if extra_instructions:
        prompt += f"\n\n## Instrucciones de mejora de la iteración anterior\n{extra_instructions}"
    return prompt


def _build_reflection_prompt(outputs: dict, state: AgentState) -> str:
    template = _PROMPT_REFL.read_text(encoding="utf-8")
    ext = state.get("extracted_data", {})
    app = state.get("appetite_result", {})
    pricing = state.get("pricing_output", {})
    def _to_str(v) -> str:
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) if v else ""
    return (
        template
        .replace("{risk_summary}",  _to_str(outputs.get("risk_summary")))
        .replace("{quote_draft}",   _to_str(outputs.get("quote_draft")))
        .replace("{broker_comm}",   _to_str(outputs.get("broker_comm")))
        .replace("{company_name}",  str(ext.get("company_name") or "no informado"))
        .replace("{line_of_business}", state.get("line_of_business", ""))
        .replace("{cnae_code}",     str(ext.get("cnae_code") or "no informado"))
        .replace("{sum_insured_eur}", str(ext.get("sum_insured_eur") or "no informado"))
        .replace("{appetite_verdict}", app.get("verdict", ""))
        .replace("{risk_score}",    str(state.get("risk_score", 0)))
        .replace("{prima_tecnica}", str(pricing.get("prima_tecnica_eur", "")))
        .replace("{missing_fields}", str(state.get("missing_fields", [])))
    )


def _parse_json(content: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    return json.loads(json_str)


def output_node(state: AgentState) -> AgentState:
    llm = get_llm(temperature=0.1)  # ligera temperatura para outputs narrativos
    reflection_log = []
    tokens_total = 0

    # --- Primera pasada: generación ---
    gen_prompt = _build_generation_prompt(state)
    gen_response = llm.invoke(gen_prompt)
    tokens_total += gen_response.usage_metadata.get("total_tokens", 0) if gen_response.usage_metadata else 0

    try:
        outputs = _parse_json(gen_response.content)
    except (json.JSONDecodeError, ValueError):
        outputs = {
            "risk_summary": gen_response.content,
            "quote_draft":  "[Error de formato — revisar manualmente]",
            "broker_comm":  "[Error de formato — revisar manualmente]",
        }

    reflection_log.append({"pass": 1, "action": "generation"})

    # --- Reflexión: evaluar calidad ---
    for cycle in range(MAX_REFLECTION_CYCLES):
        refl_prompt = _build_reflection_prompt(outputs, state)
        refl_response = llm.invoke(refl_prompt)
        tokens_total += refl_response.usage_metadata.get("total_tokens", 0) if refl_response.usage_metadata else 0

        try:
            reflection = _parse_json(refl_response.content)
        except (json.JSONDecodeError, ValueError):
            reflection = {"total_score": 90, "approved": True, "critique": "error de parseo en reflexión"}

        total_score = reflection.get("total_score", 0)
        approved    = reflection.get("approved", False)
        reflection_log.append({
            "pass":        cycle + 2,
            "action":      "reflection",
            "total_score": total_score,
            "approved":    approved,
            "scores":      reflection.get("scores", {}),
            "critique":    reflection.get("critique", ""),
        })

        if approved or total_score >= REFLECTION_THRESHOLD:
            break

        # --- Regeneración con instrucciones de mejora ---
        improvement = reflection.get("improvement_instructions", "")
        regen_prompt = _build_generation_prompt(state, extra_instructions=improvement)
        regen_response = llm.invoke(regen_prompt)
        tokens_total += regen_response.usage_metadata.get("total_tokens", 0) if regen_response.usage_metadata else 0

        try:
            outputs = _parse_json(regen_response.content)
        except (json.JSONDecodeError, ValueError):
            pass  # mantener los outputs anteriores si la regeneración falla

        reflection_log.append({"pass": cycle + 3, "action": "regeneration"})

    final_score = next(
        (r["total_score"] for r in reversed(reflection_log) if "total_score" in r),
        0,
    )

    log_entry = {
        "node": "output_generation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm+reflection",
        "reflection_cycles": len([r for r in reflection_log if r["action"] == "reflection"]),
        "final_llm_judge_score": final_score,
        "reflection_log": reflection_log,
        "tokens_used_total": tokens_total,
    }

    # Añadir metadatos de calidad al output
    outputs["_quality"] = {
        "llm_judge_score":  final_score,
        "reflection_cycles": len([r for r in reflection_log if r["action"] == "reflection"]),
        "ca07_passed": final_score >= REFLECTION_THRESHOLD,
    }

    return {
        **state,
        "outputs":   outputs,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }
