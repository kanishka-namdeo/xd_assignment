"""Application ORM model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.session import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.applicant import Applicant


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applicants.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress"
    )  # in_progress | completed | manual_review
    current_phase: Mapped[str] = mapped_column(String(30), default="intake")
    langgraph_checkpoint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    eligibility_score: Mapped[float | None]
    decision: Mapped[str | None]  # approved | soft_decline | manual_review
    decision_explanation: Mapped[str | None]
    phase_completed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    eligibility_factors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    applicant: Mapped["Applicant"] = relationship("Applicant", back_populates="applications")
