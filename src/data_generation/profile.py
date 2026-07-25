"""ApplicantProfile seed object for cross-document consistency."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ApplicantProfile(BaseModel):
    """Single source of truth for applicant identity across all document generators.

    All 28 fields align with the application_form_data schema (22 fields) plus
    emirates_id_data schema fields (20 fields) for cross-document consistency.
    """

    full_name_en: str = Field(..., description="Full name in English")
    full_name_ar: str = Field(..., description="Full name in Arabic")
    identity_number: str = Field(..., description="15-digit Emirates ID (784-YYYY-NNNNNNN-C)")
    date_of_birth: date = Field(..., description="Date of birth")
    nationality: str = Field(..., description="Nationality")
    gender: str = Field(..., description="Gender (Male/Female)")
    contact_phone: str = Field(..., description="UAE phone number")
    contact_email: str = Field(..., description="Email address")
    address: dict[str, str] = Field(..., description="Address: {emirate, city, street, po_box}")
    marital_status: str = Field(..., description="Marital status")
    family_size: int = Field(..., description="Number of family members")
    dependents: list[dict[str, Any]] = Field(..., description="List of dependent records")
    employment_status: str = Field(..., description="Employment status")
    employer_name: str = Field(..., description="Employer name")
    occupation: str = Field(..., description="Occupation / job title")
    monthly_salary: Decimal = Field(..., description="Monthly salary in AED")
    other_income: Decimal = Field(..., description="Other monthly income in AED")
    total_monthly_income: Decimal = Field(..., description="Total monthly income in AED")
    housing_status: str = Field(..., description="Housing status")
    monthly_rent: Decimal = Field(..., description="Monthly rent in AED")
    monthly_mortgage: Decimal = Field(..., description="Monthly mortgage in AED")
    support_category: str = Field(..., description="Support category applied under")
    supporting_documents: list[str] = Field(..., description="List of supporting document types")
    is_declaration_signed: bool = Field(..., description="Whether declaration is signed")
    declaration_date: date = Field(..., description="Declaration signing date")
    mother_name: str = Field(..., description="Mother's full name")
    sponsor_name: str = Field(..., description="Sponsor's full name")
    sponsor_type: str = Field(..., description="Sponsor type (employer/family/self)")
    residency_type: str = Field(..., description="Residency type")
    residency_number: str = Field(..., description="Residency permit number")

    def to_application_form_data(self) -> dict[str, Any]:
        """Map profile to application_form_data schema (22 fields)."""
        return {
            "applicant_name": self.full_name_en,
            "identity_number": self.identity_number,
            "date_of_birth": self.date_of_birth.isoformat(),
            "nationality": self.nationality,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "address": self.address,
            "employment_status": self.employment_status,
            "total_monthly_income": str(self.total_monthly_income),
            "marital_status": self.marital_status,
            "family_size": self.family_size,
            "dependents": self.dependents,
            "employer_name": self.employer_name,
            "occupation": self.occupation,
            "monthly_salary": str(self.monthly_salary),
            "other_income": str(self.other_income),
            "housing_status": self.housing_status,
            "monthly_rent": str(self.monthly_rent),
            "monthly_mortgage": str(self.monthly_mortgage),
            "support_category": self.support_category,
            "supporting_documents": self.supporting_documents,
            "is_declaration_signed": self.is_declaration_signed,
            "declaration_date": self.declaration_date.isoformat(),
        }

    def to_emirates_id_data(self) -> dict[str, Any]:
        """Map profile to emirates_id_data schema fields."""
        return {
            "identity_number": self.identity_number,
            "full_name_en": self.full_name_en,
            "full_name_ar": self.full_name_ar,
            "nationality": self.nationality,
            "date_of_birth": self.date_of_birth.isoformat(),
            "gender": self.gender,
            "address": self.address,
            "occupation": self.occupation,
            "employer_name": self.employer_name,
            "marital_status": self.marital_status,
            "mother_name": self.mother_name,
            "sponsor_name": self.sponsor_name,
            "sponsor_type": self.sponsor_type,
            "residency_type": self.residency_type,
            "residency_number": self.residency_number,
        }

    @classmethod
    def generate(cls, seed: int) -> "ApplicantProfile":
        """Generate an ApplicantProfile using the applicant_generator module."""
        from src.data_generation.applicant_generator import generate_applicant

        return generate_applicant(seed)
