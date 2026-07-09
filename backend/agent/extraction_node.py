"""
Node 2 — Data Extraction.
Extrae campos estructurados del email y adjuntos usando LLM.
Detecta campos faltantes y activa HITL-1 si supera el umbral.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .state import AgentState
from ..utils.llm import get_llm

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extraction_node.md"

# Campos extraíbles del email: su ausencia activa HITL-1
CAMPOS_EMAIL = {"company_name", "sum_insured_eur", "requested_coverages"}

# Campos que vienen de adjuntos (DUDA-004): se extraen si están disponibles
# pero su ausencia NO activa HITL-1 (limitación conocida del PoC sin pdf_parser)
CAMPOS_ADJUNTO = {"cnae_code", "loss_history"}

# Todos los campos críticos (usados para logging y evaluación)
CAMPOS_CRITICOS = CAMPOS_EMAIL | CAMPOS_ADJUNTO

# Umbral: ≥1 campo de EMAIL faltante activa HITL-1
MISSING_FIELDS_HITL_THRESHOLD = 1


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


def _format_attachments(attachments) -> str:
    if not attachments:
        return "(sin adjuntos mencionados)"
    if isinstance(attachments, list):
        lines = []
        for a in attachments:
            if isinstance(a, dict):
                name = a.get("filename") or a.get("name", "adjunto")
                tipo = a.get("type", "desconocido")
                # El contenido del adjunto viene en extracted_text_summary
                # (memoria de actividad ya extraída); fallback a description
                content = a.get("extracted_text_summary") or a.get("description", "")
                lines.append(f"- {name} ({tipo}): {content}")
            else:
                lines.append(f"- {a}")
        return "\n".join(lines)
    return str(attachments)


def _load_prompt(state: AgentState) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    raw = state.get("submission_raw", {})
    metadata = state.get("metadata", {})
    broker_name = metadata.get("broker_name") or (
        raw["broker"] if isinstance(raw.get("broker"), str) else raw.get("broker", {}).get("name", "")
    )
    tomador = metadata.get("tomador")
    tomador_str = tomador if isinstance(tomador, str) else (tomador.get("name", "") if isinstance(tomador, dict) else "")
    return (
        template
        .replace("{line_of_business}", str(state.get("line_of_business", "")))
        .replace("{broker_name}", str(broker_name or ""))
        .replace("{tomador}", tomador_str)
        .replace("{email_raw}", _format_email(raw.get("email_raw", {})))
        .replace("{attachments_summary}", _format_attachments(raw.get("attachments", [])))
    )


def _parse_extraction_json(content: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = match.group(1) if match else content.strip()
    return json.loads(json_str)


def _compute_missing_fields(extracted: dict) -> list[str]:
    """Devuelve campos de EMAIL que son null — estos activan HITL-1.
    Los campos de adjunto (cnae_code, loss_history) no se incluyen aunque sean null:
    su ausencia es una limitación conocida del PoC (DUDA-004, sin pdf_parser)."""
    missing = []
    for campo in CAMPOS_EMAIL:
        val = extracted.get(campo)
        if val is None or val == "":
            missing.append(campo)
        elif isinstance(val, list) and len(val) == 0:
            # requested_coverages vacío sí es faltante
            missing.append(campo)
    return missing


def extraction_node(state: AgentState) -> AgentState:
    llm = get_llm(temperature=0.0)
    prompt = _load_prompt(state)

    response = llm.invoke(prompt)
    content = response.content

    try:
        parsed = _parse_extraction_json(content)
        extracted_data = parsed.get("extracted_data", {})
        # Recalcular missing_fields siempre desde los datos reales (no fiar del LLM)
        missing_fields = _compute_missing_fields(extracted_data)
        extraction_notes = parsed.get("extraction_notes", "")
        extraction_confidence = parsed.get("extraction_confidence", "low")
    except (json.JSONDecodeError, ValueError):
        extracted_data = {}
        missing_fields = list(CAMPOS_CRITICOS)
        extraction_notes = f"Error al parsear respuesta del LLM: {content[:200]}"
        extraction_confidence = "low"

    log_entry = {
        "node": "data_extraction",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "llm",
        "fields_extracted": [k for k, v in extracted_data.items() if v is not None and v != [] and v != ""],
        "missing_fields": missing_fields,
        "extraction_confidence": extraction_confidence,
        "extraction_notes": extraction_notes,
        "tokens_used": getattr(response, "usage_metadata", {}) or {},
    }
    return {
        **state,
        "extracted_data": extracted_data,
        "missing_fields": missing_fields,
        "audit_log": state.get("audit_log", []) + [log_entry],
    }


def route_after_extraction(state: AgentState) -> str:
    """Arista condicional: campos críticos faltantes → HITL-1, completo → appetite."""
    if len(state.get("missing_fields", [])) >= MISSING_FIELDS_HITL_THRESHOLD:
        return "hitl_point_1"
    return "appetite_validation"
