"""Audit ORM models - document audit trail and processing queue."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.infrastructure.db.session import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.document import Document


class AuditLog(Base):
    __tablename__ = "document_audit_log"
    __table_args__ = (
        CheckConstraint(
            "performed_by_type IN ('user', 'system', 'agent')",
            name="chk_audit_performed_by_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(nullable=False)
    performed_by: Mapped[str] = mapped_column(nullable=False)
    performed_by_type: Mapped[str] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    previous_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None]
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    hash: Mapped[str] = mapped_column(nullable=False)
    previous_hash: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="audit_logs"
    )


class ProcessingQueue(Base):
    __tablename__ = "document_processing_queue"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="processing_queue"
    )
