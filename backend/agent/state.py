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
    missing_fields_at_extraction: list[str]  # snapshot de missing_fields en extracción, antes de que el resume de HITL-1 lo vacíe (solo evaluación/CA-03)

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
