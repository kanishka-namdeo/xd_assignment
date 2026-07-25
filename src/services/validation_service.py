"""Validation service - single document and cross-document validation."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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

logger = structlog.get_logger()


class ValidationService:
    """Orchestrate document validation and cross-document consistency checks."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.emirates_id_repo = EmiratesIDRepository(session)
        self.bank_stmt_repo = BankStatementRepository(session)
        self.credit_report_repo = CreditReportRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.assets_liabilities_repo = AssetsLiabilitiesRepository(session)
        self.application_form_repo = ApplicationFormRepository(session)
        self.validation_repo = CrossDocumentValidationRepository(session)

    async def validate_document(self, document_id: UUID) -> dict:
        """Validate a single document's extracted data."""
        document = await self.doc_repo.get_by_id(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        await self.doc_repo.update_status(document_id, processing_status="validating")

        validation_result = self._run_single_validation(document)

        status = "valid" if validation_result["is_valid"] else "warnings"
        if validation_result.get("errors"):
            status = "invalid"

        await self.doc_repo.update_status(
            document_id,
            processing_status="completed",
            validation_status=status,
        )

        logger.info(
            "document_validated",
            document_id=str(document_id),
            status=status,
            issues=len(validation_result.get("issues", [])),
        )
        return validation_result

    async def validate_cross_document(self, applicant_id: UUID) -> dict:
        """Run cross-document consistency validation for an applicant."""
        documents = await self.doc_repo.get_by_applicant(applicant_id)
        completed_docs = [d for d in documents if d.processing_status == "completed"]

        if len(completed_docs) < 2:
            return {
                "status": "insufficient_documents",
                "message": "Need at least 2 completed documents for cross-validation",
                "document_count": len(completed_docs),
            }

        findings, discrepancies = self._run_cross_validation(completed_docs)

        doc_ids = [d.id for d in completed_docs]
        doc_types = [d.document_type for d in completed_docs]

        has_discrepancies = len(discrepancies) > 0
        confidence = 1.0 - (len(discrepancies) * 0.1)
        confidence = max(0.0, min(1.0, confidence))

        validation = await self.validation_repo.create(
            applicant_id=applicant_id,
            validation_type="cross_document_consistency",
            source_documents=doc_ids,
            source_document_types=doc_types,
            status="discrepancies_found" if has_discrepancies else "passed",
            confidence_score=confidence,
            findings=findings,
            discrepancies=discrepancies if has_discrepancies else None,
        )

        logger.info(
            "cross_document_validation",
            applicant_id=str(applicant_id),
            documents=len(completed_docs),
            discrepancies=len(discrepancies),
            confidence=confidence,
        )
        return {
            "validation_id": str(validation.id),
            "status": validation.status,
            "confidence": confidence,
            "findings": findings,
            "discrepancies": discrepancies,
        }

    async def get_validation_results(self, applicant_id: UUID) -> list[dict]:
        """Get all validation results for an applicant."""
        validations = await self.validation_repo.get_by_applicant(applicant_id)
        return [
            {
                "id": str(v.id),
                "validation_type": v.validation_type,
                "status": v.status,
                "confidence_score": v.confidence_score,
                "findings": v.findings,
                "discrepancies": v.discrepancies,
                "is_resolved": v.is_resolved,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in validations
        ]

    async def resolve_discrepancy(
        self, validation_id: UUID, resolved_by: str, resolution_notes: str | None = None
    ) -> dict | None:
        """Mark a cross-document discrepancy as resolved."""
        validation = await self.validation_repo.resolve(
            validation_id, resolved_by, resolution_notes
        )
        if validation is None:
            return None

        logger.info(
            "discrepancy_resolved",
            validation_id=str(validation_id),
            resolved_by=resolved_by,
        )
        return {
            "id": str(validation.id),
            "status": "resolved",
            "resolved_by": validation.resolved_by,
            "resolution_notes": validation.resolution_notes,
        }

    def _run_single_validation(self, document) -> dict:
        """Run validation rules on a single document.

        Placeholder for document-type-specific validation logic.
        """
        issues: list[str] = []
        errors: list[str] = []

        if document.file_size_bytes is not None and document.file_size_bytes == 0:
            errors.append("File is empty")

        if document.file_hash is None:
            errors.append("Missing file hash")

        return {
            "document_id": str(document.id),
            "document_type": document.document_type,
            "is_valid": len(errors) == 0,
            "issues": issues,
            "errors": errors,
        }

    def _run_cross_validation(self, documents: list) -> tuple[dict, list[dict]]:
        """Run cross-document consistency checks.

        Placeholder for identity, income, address, and employment cross-checks.
        """
        findings: dict = {
            "identity_match": True,
            "income_consistency": True,
            "address_consistency": True,
            "employment_consistency": True,
        }
        discrepancies: list[dict] = []

        doc_types = {d.document_type for d in documents}
        if "emirates_id" not in doc_types:
            discrepancies.append({
                "type": "missing_document",
                "severity": "high",
                "message": "Emirates ID not found - cannot verify identity",
            })
            findings["identity_match"] = False

        return findings, discrepancies
