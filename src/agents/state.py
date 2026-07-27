"""Shared AgentState TypedDict with reducers."""

import operator
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class ApplicantState(TypedDict):
    """State shared across all agents in the 7-phase applicant flow."""

    messages: Annotated[list[dict[str, Any]], add_messages]
    current_phase: str
    applicant_id: str
    application_id: str
    uploaded_files: list[str]
    eligibility_score: float | None
    decision: str | None
    decision_explanation: str | None
    uploaded_documents: Annotated[list[dict[str, str]], operator.add]
    discrepancies: Annotated[list[dict[str, Any]], operator.add]
    extracted_data: dict[str, Any]
    validation_errors: Annotated[list[str], operator.add]
    identity_number: str | None
    support_category: str | None
    extraction_confidence: dict[str, float]
    validation_results: dict
    validation_confidence: float | None
    eligibility_factors: dict | None
    gate_status: str
    gate_errors: Annotated[list[str], operator.add]
    retry_count: int
    escalation_reason: str | None
    applicant_info: dict[str, Any]
    extraction_results: Annotated[list[dict[str, Any]], operator.add]
    _next_action: str | None
    _clarification_questions: Annotated[list[dict[str, Any]], operator.add]
    enablement_recommendations: Annotated[list[str], operator.add]
    new_documents_uploaded: bool
