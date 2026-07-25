"""Eligibility request/response schemas."""

from uuid import UUID

from pydantic import BaseModel


class EligibilityResponse(BaseModel):
    application_id: UUID
    eligibility_score: float
    factors: dict | None = None


class EligibilityExplanationResponse(BaseModel):
    application_id: UUID
    explanation: str
    eligibility_score: float


class EligibilityComputeResponse(BaseModel):
    application_id: UUID
    eligibility_score: float
    factors: dict
    features_used: list[str]
