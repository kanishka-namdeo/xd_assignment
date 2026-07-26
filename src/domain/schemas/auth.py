"""Auth request/response schemas."""

from pydantic import BaseModel
from uuid import UUID


class AuthLoginRequest(BaseModel):
    emirates_id: str


class AuthLoginResponse(BaseModel):
    applicant_id: UUID
    application_id: UUID
    is_new_applicant: bool
    current_phase: str
    state_snapshot: dict | None = None
