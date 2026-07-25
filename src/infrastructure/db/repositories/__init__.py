from src.infrastructure.db.repositories.applicant_repo import ApplicantRepository
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.audit_repo import AuditLogRepository, ProcessingQueueRepository
from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.db.repositories.extraction_repo import (
    ApplicationFormRepository,
    AssetsLiabilitiesRepository,
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
    ResumeRepository,
)
from src.infrastructure.db.repositories.validation_repo import CrossDocumentValidationRepository

__all__ = [
    "ApplicantRepository",
    "ApplicationRepository",
    "AuditLogRepository",
    "ApplicationFormRepository",
    "AssetsLiabilitiesRepository",
    "BankStatementRepository",
    "CreditReportRepository",
    "CrossDocumentValidationRepository",
    "DocumentRepository",
    "EmiratesIDRepository",
    "ProcessingQueueRepository",
    "ResumeRepository",
]
