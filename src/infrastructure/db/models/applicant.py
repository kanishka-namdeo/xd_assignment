"""Applicant ORM model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.session import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.application import Application


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identity_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str | None]
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None]
    phone: Mapped[str | None]
    email: Mapped[str | None]
    address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    marital_status: Mapped[str | None]
    family_size: Mapped[int | None]
    employment_status: Mapped[str | None]
    employer_name: Mapped[str | None]
    occupation: Mapped[str | None]
    housing_status: Mapped[str | None]
    support_category: Mapped[str | None]
    monthly_salary: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="applicant", cascade="all, delete-orphan"
    )
