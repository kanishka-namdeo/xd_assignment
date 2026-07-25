"""Extraction ORM models - document-type-specific extracted data."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.session import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.document import Document


class EmiratesIDData(Base):
    __tablename__ = "emirates_id_data"
    __table_args__ = (
        CheckConstraint(
            "gender IN ('Male', 'Female')", name="chk_emirates_id_gender"
        ),
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_emirates_id_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    identity_number: Mapped[str] = mapped_column(unique=True, nullable=False)
    full_name_en: Mapped[str] = mapped_column(nullable=False)
    full_name_ar: Mapped[str | None]
    nationality: Mapped[str] = mapped_column(nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(nullable=False)
    card_number: Mapped[str | None]
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_mrz_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occupation: Mapped[str | None]
    employer_name: Mapped[str | None]
    marital_status: Mapped[str | None]
    mother_name: Mapped[str | None]
    sponsor_name: Mapped[str | None]
    sponsor_type: Mapped[str | None]
    residency_type: Mapped[str | None]
    residency_number: Mapped[str | None]
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="emirates_id_data"
    )


class BankStatementData(Base):
    __tablename__ = "bank_statement_data"
    __table_args__ = (
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_bank_stmt_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bank_name: Mapped[str] = mapped_column(nullable=False)
    account_holder_name: Mapped[str] = mapped_column(nullable=False)
    account_number: Mapped[str] = mapped_column(nullable=False)
    iban: Mapped[str | None]
    account_type: Mapped[str | None]
    currency: Mapped[str] = mapped_column(default="AED", nullable=False)
    statement_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    statement_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_debits: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_credits: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_balance_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    transactions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="bank_statement_data"
    )
    transactions_list: Mapped[list["BankStatementTransaction"]] = relationship(
        "BankStatementTransaction", back_populates="bank_statement", cascade="all, delete-orphan"
    )


class BankStatementTransaction(Base):
    __tablename__ = "bank_statement_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('debit', 'credit')", name="chk_bank_txn_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_statement_data.id", ondelete="CASCADE"), nullable=False
    )
    transaction_hash: Mapped[str] = mapped_column(unique=True, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(nullable=False)
    running_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    category: Mapped[str | None]
    counterparty: Mapped[str | None]
    reference_number: Mapped[str | None]
    is_wps_salary: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str | None]
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_bounding_box: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    bank_statement: Mapped["BankStatementData"] = relationship(
        "BankStatementData", back_populates="transactions_list"
    )


class CreditReportData(Base):
    __tablename__ = "credit_report_data"
    __table_args__ = (
        CheckConstraint(
            "credit_score >= 300 AND credit_score <= 900", name="chk_credit_score_range"
        ),
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_credit_report_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    cb_subject_id: Mapped[str] = mapped_column(nullable=False)
    identity_number: Mapped[str] = mapped_column(nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    contact_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    employment_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(nullable=False)
    score_calculation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_active_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    total_closed_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    total_outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    credit_utilization_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    active_facilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    closed_facilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payment_history: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    late_payment_count: Mapped[int] = mapped_column(Integer, default=0)
    defaulted_accounts: Mapped[int] = mapped_column(Integer, default=0)
    bounced_cheques: Mapped[int] = mapped_column(Integer, default=0)
    court_judgments: Mapped[int] = mapped_column(Integer, default=0)
    has_bankruptcy_records: Mapped[bool] = mapped_column(Boolean, default=False)
    inquiry_count: Mapped[int] = mapped_column(Integer, default=0)
    inquiries: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="credit_report_data"
    )
    facilities: Mapped[list["CreditFacility"]] = relationship(
        "CreditFacility", back_populates="credit_report", cascade="all, delete-orphan"
    )


class CreditFacility(Base):
    __tablename__ = "credit_facilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_report_data.id", ondelete="CASCADE"), nullable=False
    )
    facility_type: Mapped[str] = mapped_column(nullable=False)
    lender_name: Mapped[str] = mapped_column(nullable=False)
    account_number: Mapped[str | None]
    status: Mapped[str] = mapped_column(nullable=False)
    opened_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    payment_status: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    credit_report: Mapped["CreditReportData"] = relationship(
        "CreditReportData", back_populates="facilities"
    )


class ResumeData(Base):
    __tablename__ = "resume_data"
    __table_args__ = (
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_resume_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    full_name: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str | None]
    phone: Mapped[str | None]
    location: Mapped[str | None]
    summary: Mapped[str | None]
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_experience: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    current_employer: Mapped[str | None]
    current_job_title: Mapped[str | None]
    education: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    highest_degree: Mapped[str | None]
    skills: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    skill_count: Mapped[int] = mapped_column(Integer, default=0)
    certifications: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="resume_data"
    )
    work_experience_list: Mapped[list["ResumeWorkExperience"]] = relationship(
        "ResumeWorkExperience", back_populates="resume", cascade="all, delete-orphan"
    )


class ResumeWorkExperience(Base):
    __tablename__ = "resume_work_experience"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_data.id", ondelete="CASCADE"), nullable=False
    )
    job_title: Mapped[str] = mapped_column(nullable=False)
    company: Mapped[str] = mapped_column(nullable=False)
    location: Mapped[str | None]
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None]
    achievements: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    industry: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    resume: Mapped["ResumeData"] = relationship(
        "ResumeData", back_populates="work_experience_list"
    )


class AssetsLiabilitiesData(Base):
    __tablename__ = "assets_liabilities_data"
    __table_args__ = (
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_assets_liabilities_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    applicant_name: Mapped[str] = mapped_column(nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_and_deposits: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    savings_accounts: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    investment_accounts: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    retirement_accounts: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    real_estate_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    vehicle_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    other_assets: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    mortgage_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    personal_loans: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    credit_card_debt: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    student_loans: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    other_liabilities: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_liabilities: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    net_worth: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    income_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    asset_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    liability_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="assets_liabilities_data"
    )


class ApplicationFormData(Base):
    __tablename__ = "application_form_data"
    __table_args__ = (
        CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="chk_application_form_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    applicant_name: Mapped[str] = mapped_column(nullable=False)
    identity_number: Mapped[str] = mapped_column(nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    nationality: Mapped[str] = mapped_column(nullable=False)
    contact_phone: Mapped[str] = mapped_column(nullable=False)
    contact_email: Mapped[str | None]
    address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    marital_status: Mapped[str | None]
    family_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependents: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    employment_status: Mapped[str] = mapped_column(nullable=False)
    employer_name: Mapped[str | None]
    occupation: Mapped[str | None]
    monthly_salary: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    other_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_monthly_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    housing_status: Mapped[str | None]
    monthly_rent: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    monthly_mortgage: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    support_category: Mapped[str | None]
    supporting_documents: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_declaration_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    declaration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="application_form_data"
    )


class DocumentExtractionField(Base):
    __tablename__ = "document_extraction_fields"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="chk_extraction_field_confidence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(nullable=False)
    field_value: Mapped[str | None]
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_bounding_box: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_text: Mapped[str | None]
    validation_status: Mapped[str | None]
    validation_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="extraction_fields"
    )
