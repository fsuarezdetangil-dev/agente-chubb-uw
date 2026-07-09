"""
Node 1 — Submission Intake.
Clasifica la línea de negocio y extrae metadata del broker usando LLM.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm


def _format_email(email_raw) -> str:
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

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "intake_node.md"


def _load_prompt(state: AgentState) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    raw = state.get("submission_raw", {})
    return (
        template
        .replace("{channel}", state.get("channel", "email"))
        .replace("{line_of_business}", state.get("line_of_business", ""))
        .replace("{email_raw}", _format_email(raw.get("email_raw", {})))
    )


def _parse_intake_json(content: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    return json.loads(json_str)


def intake_node(state: AgentState) -> AgentState:
    llm = get_llm(temperature=0.0)
    prompt = _load_prompt(state)

    response = llm.invoke(prompt)
    content = response.content

    try:
        parsed = _parse_intake_json(content)
        line_of_business = parsed.get("line_of_business", state.get("line_of_business", "property"))
        channel = parsed.get("channel", state.get("channel", "email"))
        metadata = parsed.get("metadata", {})
        metadata["classification_confidence"] = parsed.get("classification_confidence", "low")
        metadata["classification_reasoning"] = parsed.get("classification_reasoning", "")
    except (json.JSONDecodeError, ValueError):
        # Mantener los valores del estado si el LLM falla
        line_of_business = state.get("line_of_business", "property")
        channel = state.get("channel", "email")
        metadata = state.get("metadata", {})
        metadata["classification_confidence"] = "low"
        metadata["parse_error"] = content[:200]

    log_entry = {
        "node": "submission_intake",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm",
        "line_of_business": line_of_business,
        "channel": channel,
        "classification_confidence": metadata.get("classification_confidence"),
        "tokens_used": getattr(response, "usage_metadata", {}) or {},
    }
    return {
        **state,
        "line_of_business": line_of_business,
        "channel": channel,
        "metadata": metadata,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }
