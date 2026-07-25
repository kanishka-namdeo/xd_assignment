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
