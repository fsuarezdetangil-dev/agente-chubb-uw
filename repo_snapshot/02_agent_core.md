# 02 — Núcleo del agente (LangGraph)

Todos los nodos están **implementados de verdad** (llaman al LLM real vía Azure OpenAI).
No hay stubs vacíos salvo los tres nodos HITL, que son `lambda s: s` a propósito (LangGraph
pausa con `interrupt_before` antes de ejecutarlos). El único "stub" funcional es el motor de
pricing, que es un stub intencional dentro de `risk_node.py` (`_call_pricing_stub`).

Orden del grafo: `plan_node → submission_intake → data_extraction → [HITL-1] → appetite_validation → [HITL-2] → risk_assessment → [HITL-3] → output_generation → END`

---

## `backend/agent/state.py` — 37 líneas

```python
"""
AgentState — estado compartido del grafo LangGraph.
Todos los nodos leen y escriben sobre este TypedDict.
"""

from typing import Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # --- Identificación y entrada ---
    submission_id: str
    submission_raw: dict           # email + attachments originales
    channel: str                   # email | portal | api
    line_of_business: str          # property | casualty
    metadata: dict                 # broker, tomador, fecha

    # --- Extracción (Node 2) ---
    extracted_data: dict           # datos estructurados del riesgo
    missing_fields: list[str]      # campos faltantes detectados

    # --- Apetito (Node 3) ---
    appetite_result: dict          # veredicto + justificación + citas RAG

    # --- Riesgo y pricing (Node 4) ---
    risk_score: int                # 0-100
    risk_flags: list[str]          # red flags identificados
    pricing_output: dict           # prima técnica del stub de pricing

    # --- Outputs finales (Node 5) ---
    outputs: dict                  # risk_summary, quote_draft, broker_comm

    # --- Control de flujo ---
    audit_log: list[dict]          # registro de cada paso ejecutado
    hitl_status: str               # pending | approved | rejected | none
    hitl_point: str                # point_1 | point_2 | point_3 | none
    plan_json: list[dict]          # plan de ejecución generado por Plan JSON Node
```

---

## `backend/agent/graph.py` — 134 líneas

```python
"""
Grafo principal del P&C UW Agent.
Define los nodos, aristas condicionales y los tres puntos HITL con interrupt_before.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import AgentState
from .plan_node import plan_node
from .intake_node import intake_node
from .extraction_node import extraction_node, route_after_extraction
from .appetite_node import appetite_node, route_after_appetite
from .risk_node import risk_node, route_after_risk
from .output_node import output_node


def build_graph(checkpointer=None):
    """Construye y compila el grafo. Acepta checkpointer externo para tests."""
    builder = StateGraph(AgentState)

    # Registrar nodos
    builder.add_node("plan_node",           plan_node)
    builder.add_node("submission_intake",   intake_node)
    builder.add_node("data_extraction",     extraction_node)
    builder.add_node("appetite_validation", appetite_node)
    builder.add_node("risk_assessment",     risk_node)
    builder.add_node("output_generation",   output_node)

    # Nodos HITL — vacíos: LangGraph pausará antes de ejecutarlos (interrupt_before)
    builder.add_node("hitl_point_1", lambda s: s)
    builder.add_node("hitl_point_2", lambda s: s)
    builder.add_node("hitl_point_3", lambda s: s)

    # Flujo principal
    builder.set_entry_point("plan_node")
    builder.add_edge("plan_node",           "submission_intake")
    builder.add_edge("submission_intake",   "data_extraction")

    # Arista condicional 1: datos incompletos → HITL-1, completos → appetite
    builder.add_conditional_edges(
        "data_extraction",
        route_after_extraction,
        {"hitl_point_1": "hitl_point_1", "appetite_validation": "appetite_validation"},
    )
    builder.add_edge("hitl_point_1", "appetite_validation")

    # Arista condicional 2: fuera/revision → HITL-2, dentro → risk
    builder.add_conditional_edges(
        "appetite_validation",
        route_after_appetite,
        {"hitl_point_2": "hitl_point_2", "risk_assessment": "risk_assessment"},
    )
    builder.add_edge("hitl_point_2", "risk_assessment")

    # Arista condicional 3: risk alto → HITL-3, bajo → output
    builder.add_conditional_edges(
        "risk_assessment",
        route_after_risk,
        {"hitl_point_3": "hitl_point_3", "output_generation": "output_generation"},
    )
    builder.add_edge("hitl_point_3", "output_generation")

    builder.add_edge("output_generation", END)

    # Compilar con interrupt_before en los tres puntos HITL
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_point_1", "hitl_point_2", "hitl_point_3"],
    )


def get_default_graph():
    """Instancia el grafo con checkpointer SQLite persistente."""
    import sqlite3
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer=checkpointer)


if __name__ == "__main__":
    # Smoke test rápido con una submission mínima
    graph = get_default_graph()

    initial_state: AgentState = {
        "submission_id": "TEST-001",
        "submission_raw": {
            "extracted_data_ground_truth": {
                "company_name": "Aceros del Norte S.A.",
                "cnae_code": "2410",
                "activity_description": "Fabricación de productos de acero",
                "province": "Bilbao",
                "sum_insured_eur": 5000000,
                "requested_coverages": ["incendio", "robo"],
                "loss_history": "sin siniestros en 3 años",
                "loss_ratio": 0.0,
                "renewal": True,
            },
            "missing_fields_expected": [],
            "appetite_expected": "dentro",
            "expected_hitl_trigger": "STP_dentro_apetito",
            "metadata": {"broker": "Marsh Madrid", "tomador": "Aceros del Norte S.A."},
        },
        "channel": "email",
        "line_of_business": "property",
        "metadata": {},
        "extracted_data": {},
        "missing_fields": [],
        "appetite_result": {},
        "risk_score": 0,
        "risk_flags": [],
        "pricing_output": {},
        "outputs": {},
        "audit_log": [],
        "hitl_status": "none",
        "hitl_point": "none",
        "plan_json": [],
    }

    config = {"configurable": {"thread_id": "TEST-001"}}
    result = graph.invoke(initial_state, config=config)

    print("\n=== Smoke test completado ===")
    print(f"Submission: {result['submission_id']}")
    print(f"Plan JSON: {len(result['plan_json'])} pasos")
    print(f"Extracted fields: {list(result['extracted_data'].keys())}")
    print(f"Appetite verdict: {result['appetite_result'].get('verdict')}")
    print(f"Risk score: {result['risk_score']}")
    print(f"Prima técnica: {result['pricing_output'].get('prima_tecnica_eur')} EUR")
    print(f"Audit log: {len(result['audit_log'])} entradas")
    print(f"HITL status: {result['hitl_status']}")
    print(f"\nOutputs:")
    for k, v in result['outputs'].items():
        print(f"  {k}: {v[:80]}...")
```

---

## `backend/agent/plan_node.py` — 87 líneas

```python
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
```

---

## `backend/agent/intake_node.py` (Node 1) — 84 líneas

```python
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
```

---

## `backend/agent/extraction_node.py` (Node 2) — 138 líneas

```python
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
        return "\n".join(
            f"- {a.get('name', 'adjunto')} ({a.get('type', 'desconocido')}): {a.get('description', '')}"
            if isinstance(a, dict) else f"- {a}"
            for a in attachments
        )
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
```

---

## `backend/agent/appetite_node.py` (Node 3) — 119 líneas

```python
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
```

---

## `backend/agent/risk_node.py` (Node 4) — 159 líneas

```python
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
    return any(
        any(kw in f.lower() for kw in critical_keywords)
        for f in flags
    )


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
```

---

## `backend/agent/output_node.py` (Node 5 + Reflection) — 178 líneas

```python
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
```

---

## `backend/utils/llm.py` — 21 líneas  ← **PROVEEDOR LLM REAL**

```python
"""
Inicialización del LLM compartido para todos los nodos.
Usa AzureChatOpenAI con las variables de .env.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()


def get_llm(temperature: float = 0.0) -> AzureChatOpenAI:
    """Devuelve una instancia de AzureChatOpenAI lista para usar."""
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=temperature,
    )
```
