"""Document ORM model - base table for all document types."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.session import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.extraction import (
        ApplicationFormData,
        AssetsLiabilitiesData,
        BankStatementData,
        CreditReportData,
        EmiratesIDData,
        ResumeData,
    )
    from src.infrastructure.db.models.audit import AuditLog, ProcessingQueue
    from src.infrastructure.db.models.extraction import DocumentExtractionField


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('emirates_id', 'bank_statement', 'credit_report', 'resume', 'assets_liabilities', 'application_form')",
            name="chk_document_type",
        ),
        CheckConstraint(
            "overall_confidence >= 0.0 AND overall_confidence <= 1.0",
            name="chk_overall_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    applicant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="uploaded", nullable=False
    )  # uploaded, classifying, extracting, validating, completed, failed, archived
    file_path: Mapped[str] = mapped_column(nullable=False)
    file_format: Mapped[str | None]  # pdf, xlsx, jpg, png, docx
    file_size_bytes: Mapped[int | None]
    file_hash: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extraction_status: Mapped[str | None] = mapped_column(
        default="pending"
    )  # pending, success, partial, failed
    validation_status: Mapped[str | None] = mapped_column(
        default="pending"
    )  # pending, valid, invalid, warnings
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    doc_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    error_log: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # One-to-one relationships with extraction tables
    emirates_id_data: Mapped["EmiratesIDData | None"] = relationship(
        "EmiratesIDData", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    bank_statement_data: Mapped["BankStatementData | None"] = relationship(
        "BankStatementData", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    credit_report_data: Mapped["CreditReportData | None"] = relationship(
        "CreditReportData", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    resume_data: Mapped["ResumeData | None"] = relationship(
        "ResumeData", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    assets_liabilities_data: Mapped["AssetsLiabilitiesData | None"] = relationship(
        "AssetsLiabilitiesData",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    application_form_data: Mapped["ApplicationFormData | None"] = relationship(
        "ApplicationFormData",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One-to-many relationships (audit, queue, extraction fields)
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="document", cascade="all, delete-orphan"
    )
    processing_queue: Mapped[list["ProcessingQueue"]] = relationship(
        "ProcessingQueue", back_populates="document", cascade="all, delete-orphan"
    )
    extraction_fields: Mapped[list["DocumentExtractionField"]] = relationship(
        "DocumentExtractionField", back_populates="document", cascade="all, delete-orphan"
    )
