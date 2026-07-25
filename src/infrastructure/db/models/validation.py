"""Validation ORM models - cross-document validation results."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from src.infrastructure.db.session import Base


class CrossDocumentValidation(Base):
    __tablename__ = "cross_document_validations"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="chk_cross_val_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    applicant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    validation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_documents: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), nullable=False)
    source_document_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    findings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    discrepancies: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_notes: Mapped[str | None]
    resolved_by: Mapped[str | None]
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
