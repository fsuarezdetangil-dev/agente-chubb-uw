"""
Plan JSON Node — genera el plan de ejecución antes de que el agente actúe.
Llama al LLM con el email raw y devuelve un plan estructurado en JSON.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm


def _format_email(email_raw) -> str:
    """Normaliza email_raw a string independientemente de si es dict o str."""
    if isinstance(email_raw, dict):
        lines = []
        if email_raw.get("from"):
            lines.append(f"De: {email_raw['from']}")
        if email_raw.get("subject"):
            lines.append(f"Asunto: {email_raw['subject']}")
        if email_raw.get("body"):
            lines.append(f"\n{email_raw['body']}")
        return "\n".join(lines)
    return str(email_raw) if email_raw else "(sin email)"

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "plan_node.md"


def _load_prompt(state: AgentState) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    raw = state.get("submission_raw", {})
    # Reemplazar manualmente para evitar KeyError con llaves {} del bloque JSON del prompt
    return (
        template
        .replace("{channel}", state.get("channel", "email"))
        .replace("{line_of_business}", state.get("line_of_business", ""))
        .replace("{email_raw}", _format_email(raw.get("email_raw", {})))
    )


def _parse_plan_json(content: str) -> list[dict]:
    """Extrae el array JSON de la respuesta del LLM, tolerando markdown fences."""
    # Intentar extraer bloque ```json ... ```
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    parsed = json.loads(json_str)
    if not isinstance(parsed, list):
        raise ValueError(f"Se esperaba una lista, se recibió: {type(parsed)}")
    return parsed


def plan_node(state: AgentState) -> AgentState:
    llm = get_llm(temperature=0.0)
    prompt = _load_prompt(state)

    response = llm.invoke(prompt)
    content = response.content

    try:
        plan_json = _parse_plan_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback al plan estático si el LLM no devuelve JSON válido
        plan_json = [
            {"step": i + 1, "node": n, "description": d, "anticipation": "n/a", "parse_error": str(e)}
            for i, (n, d) in enumerate([
                ("submission_intake",   "Clasificar línea de negocio y metadata"),
                ("data_extraction",     "Extraer campos estructurados"),
                ("appetite_validation", "Verificar apetito via RAG"),
                ("risk_assessment",     "Puntuar riesgo e invocar pricing"),
                ("output_generation",   "Generar outputs finales"),
            ])
        ]

    log_entry = {
        "node": "plan_node",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm",
        "plan_steps": len(plan_json),
        "tokens_used": getattr(response, "usage_metadata", {}) or {},
    }
    return {
        **state,
        "plan_json": plan_json,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }
