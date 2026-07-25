"""Pydantic models for Neo4j graph nodes and relationships."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicantNode(BaseModel):
    """Neo4j :Applicant node properties."""

    id: UUID
    identity_number: str
    full_name: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    phone: str | None = None
    email: str | None = None
    created_at: datetime | None = None


class FamilyMemberNode(BaseModel):
    """Neo4j :FamilyMember node properties."""

    id: UUID = Field(default_factory=UUID)
    full_name: str
    relationship: str  # spouse, child, parent, sibling
    date_of_birth: date | None = None
    nationality: str | None = None
    is_dependent: bool = False


class DocumentNode(BaseModel):
    """Neo4j :Document node properties."""

    id: UUID
    applicant_id: UUID
    document_type: str
    file_hash: str
    uploaded_at: datetime
    processing_status: str = "uploaded"
    extraction_status: str | None = None
    validation_status: str | None = None


class HasDependentRel(BaseModel):
    """(:Applicant)-[:HAS_DEPENDENT]->(:FamilyMember)"""

    since: date | None = None
    financial_dependency_ratio: float | None = None


class HasSpouseRel(BaseModel):
    """(:Applicant)-[:HAS_SPOUSE]->(:FamilyMember)"""

    married_since: date | None = None


class HasDocumentRel(BaseModel):
    """(:Applicant)-[:HAS_DOCUMENT]->(:Document)"""

    uploaded_at: datetime | None = None


class SupersedesRel(BaseModel):
    """(:Document)-[:SUPERSEDES]->(:Document) - for re-uploads"""

    superseded_at: datetime
    reason: str | None = None
