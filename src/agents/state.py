"""Shared AgentState TypedDict with reducers."""

import uuid
from typing import Annotated, Any

from langgraph.graph import add_messages


class ApplicantState(dict):
    """State shared across all agents in the 7-phase applicant flow."""

    messages: Annotated[list[dict[str, Any]], add_messages]
    current_phase: str
    applicant_id: str
    application_id: str
    uploaded_files: list[str]
    eligibility_score: float | None
    decision: str | None
    decision_explanation: str | None
    uploaded_documents: list[dict[str, str]]
    discrepancies: list[dict[str, Any]]
    extracted_data: dict[str, Any]
    validation_errors: list[str]
    identity_number: str | None
    support_category: str | None
    extraction_confidence: dict[str, float]
    validation_results: dict
    eligibility_factors: dict | None
    gate_status: str
    gate_errors: list[str]
    retry_count: int
    escalation_reason: str | None
    applicant_info: dict[str, Any]
    extraction_results: list[dict[str, Any]]
    _next_action: str | None
    _clarification_questions: list[dict[str, Any]]
    enablement_recommendations: list[str]
