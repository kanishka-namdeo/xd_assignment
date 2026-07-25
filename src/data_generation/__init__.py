"""Synthetic data generation for UAE Social Support Application testing.

All generators produce schema-compliant output with cross-document consistency.
Each generator accepts an ApplicantProfile seed and returns structured data
plus file artifacts (PDF, XLSX, DOCX, PNG).
"""

from src.data_generation.applicant_generator import generate_applicant
from src.data_generation.assets_liabilities_generator import generate_assets_liabilities
from src.data_generation.application_form_generator import generate_application_form
from src.data_generation.bank_statement_generator import generate_bank_statement
from src.data_generation.cli import generate_applicant_package, generate_batch
from src.data_generation.consistency import validate_consistency
from src.data_generation.credit_report_generator import generate_credit_report
from src.data_generation.emirates_id_generator import generate_emirates_id
from src.data_generation.profile import ApplicantProfile
from src.data_generation.resume_generator import generate_resume

__all__ = [
    "ApplicantProfile",
    "generate_applicant",
    "generate_emirates_id",
    "generate_bank_statement",
    "generate_credit_report",
    "generate_resume",
    "generate_assets_liabilities",
    "generate_application_form",
    "validate_consistency",
    "generate_applicant_package",
    "generate_batch",
]
