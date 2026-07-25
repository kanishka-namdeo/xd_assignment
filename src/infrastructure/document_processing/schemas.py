"""Pydantic schemas for document extraction results."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates for extracted content."""

    x0: float = Field(description="Left edge X coordinate")
    y0: float = Field(description="Bottom edge Y coordinate")
    x1: float = Field(description="Right edge X coordinate")
    y1: float = Field(description="Top edge Y coordinate")
    page: int = Field(description="Page number (0-indexed)")


class ExtractedField(BaseModel):
    """Single extracted field with confidence and source coordinates."""

    field_name: str
    field_value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence 0-1")
    source_page: int | None = None
    source_bounding_box: BoundingBox | None = None
    source_text: str | None = None
    validation_status: str | None = None
    validation_message: str | None = None


class ExtractionResult(BaseModel):
    """Base extraction result with metadata."""

    document_type: str
    fields: list[ExtractedField] = Field(default_factory=list)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class EmiratesIDExtracted(BaseModel):
    """Emirates ID extraction result."""

    identity_number: str
    full_name_en: str
    full_name_ar: str | None = None
    nationality: str
    date_of_birth: date
    gender: str
    card_number: str | None = None
    issue_date: date | None = None
    expiry_date: date
    is_mrz_verified: bool = False
    address: dict[str, Any] | None = None
    occupation: str | None = None
    employer_name: str | None = None
    marital_status: str | None = None
    mother_name: str | None = None
    sponsor_name: str | None = None
    sponsor_type: str | None = None
    residency_type: str | None = None
    residency_number: str | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class TransactionExtracted(BaseModel):
    """Single bank transaction."""

    transaction_date: date
    description: str
    amount: Decimal
    transaction_type: str = Field(pattern="^(debit|credit)$")
    running_balance: Decimal | None = None
    category: str | None = None
    counterparty: str | None = None
    reference_number: str | None = None
    is_wps_salary: bool = False
    channel: str | None = None
    source_page: int | None = None
    source_bounding_box: BoundingBox | None = None


class BankStatementExtracted(BaseModel):
    """Bank statement extraction result."""

    bank_name: str
    account_holder_name: str
    account_number: str
    iban: str | None = None
    account_type: str | None = None
    currency: str = "AED"
    statement_period_start: date
    statement_period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_debits: Decimal
    total_credits: Decimal
    is_balance_reconciled: bool = False
    transactions: list[TransactionExtracted] = Field(default_factory=list)
    transaction_count: int
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class CreditFacilityExtracted(BaseModel):
    """Single credit facility."""

    facility_type: str
    lender_name: str
    account_number: str | None = None
    status: str
    opened_date: date | None = None
    closed_date: date | None = None
    credit_limit: Decimal | None = None
    current_balance: Decimal
    monthly_payment: Decimal | None = None
    payment_status: str | None = None


class CreditReportExtracted(BaseModel):
    """Credit report extraction result."""

    cb_subject_id: str
    identity_number: str
    full_name: str
    contact_details: dict[str, Any] | None = None
    employment_info: dict[str, Any] | None = None
    credit_score: int = Field(ge=300, le=900)
    risk_band: str
    score_calculation_date: date | None = None
    total_active_accounts: int
    total_closed_accounts: int
    total_outstanding_balance: Decimal
    total_credit_limit: Decimal | None = None
    credit_utilization_ratio: Decimal | None = None
    active_facilities: list[CreditFacilityExtracted] = Field(default_factory=list)
    closed_facilities: list[CreditFacilityExtracted] = Field(default_factory=list)
    payment_history: dict[str, Any] | None = None
    late_payment_count: int = 0
    defaulted_accounts: int = 0
    bounced_cheques: int = 0
    court_judgments: int = 0
    has_bankruptcy_records: bool = False
    inquiry_count: int = 0
    inquiries: list[dict[str, Any]] | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class WorkExperienceExtracted(BaseModel):
    """Single work experience entry."""

    job_title: str
    company: str
    location: str | None = None
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None
    achievements: list[str] | None = None
    duration_months: int | None = None
    industry: str | None = None


class EducationExtracted(BaseModel):
    """Single education entry."""

    degree: str
    institution: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: Decimal | None = None


class ResumeExtracted(BaseModel):
    """Resume extraction result."""

    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: int | None = None
    work_experience: list[WorkExperienceExtracted] = Field(default_factory=list)
    total_positions: int
    current_employer: str | None = None
    current_job_title: str | None = None
    education: list[EducationExtracted] = Field(default_factory=list)
    highest_degree: str | None = None
    skills: list[str] = Field(default_factory=list)
    skill_count: int
    certifications: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class AssetDetailExtracted(BaseModel):
    """Single asset detail."""

    asset_type: str
    description: str
    value: Decimal
    ownership_percentage: Decimal | None = None


class LiabilityDetailExtracted(BaseModel):
    """Single liability detail."""

    liability_type: str
    description: str
    outstanding_balance: Decimal
    monthly_payment: Decimal | None = None
    interest_rate: Decimal | None = None


class AssetsLiabilitiesExtracted(BaseModel):
    """Assets and liabilities extraction result."""

    applicant_name: str
    statement_date: date
    cash_and_deposits: Decimal = Decimal("0")
    savings_accounts: Decimal = Decimal("0")
    investment_accounts: Decimal = Decimal("0")
    retirement_accounts: Decimal = Decimal("0")
    real_estate_value: Decimal = Decimal("0")
    vehicle_value: Decimal = Decimal("0")
    other_assets: Decimal = Decimal("0")
    total_assets: Decimal
    mortgage_balance: Decimal = Decimal("0")
    personal_loans: Decimal = Decimal("0")
    credit_card_debt: Decimal = Decimal("0")
    student_loans: Decimal = Decimal("0")
    other_liabilities: Decimal = Decimal("0")
    total_liabilities: Decimal
    net_worth: Decimal
    monthly_income: Decimal | None = None
    income_sources: list[dict[str, Any]] | None = None
    asset_details: list[AssetDetailExtracted] = Field(default_factory=list)
    liability_details: list[LiabilityDetailExtracted] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)
    source_coordinates: dict[str, Any] = Field(default_factory=dict)


class ApplicationFormExtracted(BaseModel):
    """Application form extraction result."""

    applicant_name: str
    identity_number: str
    date_of_birth: date
    nationality: str
    contact_phone: str
    contact_email: str | None = None
    address: dict[str, Any]
    marital_status: str | None = None
    family_size: int | None = None
    dependents: list[dict[str, Any]] | None = None
    employment_status: str
    employer_name: str | None = None
    occupation: str | None = None
    monthly_salary: Decimal | None = None
    other_income: Decimal = Decimal("0")
    total_monthly_income: Decimal
    housing_status: str | None = None
    monthly_rent: Decimal | None = None
    monthly_mortgage: Decimal | None = None
    support_category: str | None = None
    supporting_documents: list[str] | None = None
    is_declaration_signed: bool = False
    declaration_date: date | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    raw_extracted_data: dict[str, Any] = Field(default_factory=dict)


class OCRResult(BaseModel):
    """OCR extraction result with bounding boxes."""

    text: str
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    language: str = "ar+en"


class TableExtractionResult(BaseModel):
    """Table extraction result."""

    tables: list[list[list[str | None]]] = Field(default_factory=list)
    table_count: int = 0
    flavor: str = "auto"
    confidence: float = Field(ge=0.0, le=1.0)


class ConfidenceRouting(BaseModel):
    """Confidence-based routing decision."""

    overall_confidence: float
    routing_decision: str = Field(pattern="^(auto|spot_check|manual_review)$")
    field_confidences: dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: list[str] = Field(default_factory=list)
