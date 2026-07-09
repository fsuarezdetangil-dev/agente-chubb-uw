"""
Pydantic models para submissions y outputs del agente.
Estos schemas son la fuente de verdad para ground-truth y validación en evals.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ExtractedData(BaseModel):
    company_name: Optional[str] = None
    cnae_code: Optional[str] = None
    activity_description: Optional[str] = None
    province: Optional[str] = None
    sum_insured_eur: Optional[float] = None
    requested_coverages: Optional[list[str]] = None
    loss_history: Optional[str] = None
    loss_ratio: Optional[float] = None
    renewal: Optional[bool] = None


class SubmissionInput(BaseModel):
    submission_id: str
    line_of_business: str = Field(..., pattern="^(property|casualty)$")
    scenario_tag: str
    channel: str = Field(..., pattern="^(email|portal|api)$")
    broker: dict
    received_at: str
    email_raw: str
    attachments: list[dict] = []
    extracted_data_ground_truth: ExtractedData
    missing_fields_expected: list[str] = []
    appetite_expected: str = Field(..., pattern="^(dentro|fuera|revision)$")
    complete_data_expected: bool
    expected_hitl_trigger: str
    expected_hitl_trigger_reason: str
