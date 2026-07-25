"""Validation service - single document and cross-document validation."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from langfuse.decorators import observe
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.gates.completeness import validate_completeness
from src.agents.gates.document_integrity import validate_document_integrity
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

logger = structlog.get_logger(__name__)


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

    @observe(as_type="generation", name="validate_document")
    async def validate_document(self, document_id: UUID) -> dict:
        """Validate a single document's extracted data."""
        start = datetime.now(timezone.utc)
        document = await self.doc_repo.get_by_id(document_id)
        if document is None:
            logger.warning("document_not_found", document_id=str(document_id))
            raise ValueError(f"Document {document_id} not found")

        await self.doc_repo.update_status(document_id, processing_status="validating")

        # Fetch extracted data for this document
        extracted_data = await self._fetch_extracted_data(document)

        validation_result = self._run_single_validation(document, extracted_data)

        status = "valid" if validation_result["is_valid"] else "warnings"
        if validation_result.get("errors"):
            status = "invalid"

        await self.doc_repo.update_status(
            document_id,
            processing_status="completed",
            validation_status=status,
        )

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "document_validated",
            document_id=str(document_id),
            document_type=document.document_type,
            status=status,
            issues=len(validation_result.get("issues", [])),
            errors=len(validation_result.get("errors", [])),
            duration_ms=round(duration_ms, 2),
        )
        return validation_result

    @observe(as_type="generation", name="validate_cross_document")
    async def validate_cross_document(self, applicant_id: UUID, support_category: str | None = None) -> dict:
        """Run cross-document consistency validation for an applicant."""
        start = datetime.now(timezone.utc)
        documents = await self.doc_repo.get_by_applicant(applicant_id)
        completed_docs = [d for d in documents if d.processing_status == "completed"]

        if len(completed_docs) < 2:
            logger.warning(
                "insufficient_documents",
                applicant_id=str(applicant_id),
                completed_count=len(completed_docs),
                required_minimum=2,
            )
            return {
                "status": "insufficient_documents",
                "message": "Need at least 2 completed documents for cross-validation",
                "document_count": len(completed_docs),
            }

        # Fetch all extracted data
        extracted_data_by_type = await self._fetch_all_extracted_data(completed_docs)

        # Build validation results per document type
        validation_results = {}
        for doc in completed_docs:
            extracted = await self._fetch_extracted_data(doc)
            is_valid, errors = validate_document_integrity(extracted, doc.document_type)
            validation_results[doc.document_type] = {
                "is_valid": is_valid,
                "errors": errors,
            }

        # Determine required documents
        required_docs = self._get_required_documents(support_category)

        # Run completeness validation
        is_complete, missing_items = validate_completeness(
            validation_results,
            extracted_data_by_type,
            required_docs,
        )

        # Additional cross-document checks
        discrepancies = self._check_cross_document_consistency(extracted_data_by_type)

        findings = {
            "identity_match": not any("Identity number mismatch" in m for m in missing_items),
            "name_consistency": not any("Name mismatch" in m for m in missing_items),
            "dob_consistency": not any("Date of birth mismatch" in m for m in missing_items),
            "income_consistency": not any("income" in d.get("type", "").lower() for d in discrepancies),
            "address_consistency": not any("address" in d.get("type", "").lower() for d in discrepancies),
            "is_complete": is_complete,
        }

        all_issues = missing_items + [d.get("message", "") for d in discrepancies]
        has_discrepancies = len(all_issues) > 0
        confidence = 1.0 - (len(all_issues) * 0.1)
        confidence = max(0.0, min(1.0, confidence))

        doc_ids = [d.id for d in completed_docs]
        doc_types = [d.document_type for d in completed_docs]

        validation = await self.validation_repo.create(
            applicant_id=applicant_id,
            validation_type="cross_document_consistency",
            source_documents=doc_ids,
            source_document_types=doc_types,
            status="discrepancies_found" if has_discrepancies else "passed",
            confidence_score=confidence,
            findings=findings,
            discrepancies=[
                {"type": "missing_document", "severity": "high", "message": m}
                for m in missing_items
            ] + discrepancies if has_discrepancies else None,
        )

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "cross_document_validation",
            applicant_id=str(applicant_id),
            documents=len(completed_docs),
            discrepancies=len(all_issues),
            confidence=confidence,
            is_complete=is_complete,
            duration_ms=round(duration_ms, 2),
        )

        # Log individual cross-document check results
        logger.debug(
            "cross_document_checks",
            applicant_id=str(applicant_id),
            income_consistency=findings["income_consistency"],
            address_consistency=findings["address_consistency"],
            identity_match=findings["identity_match"],
            name_consistency=findings["name_consistency"],
            dob_consistency=findings["dob_consistency"],
        )

        return {
            "validation_id": str(validation.id),
            "status": validation.status,
            "confidence": confidence,
            "findings": findings,
            "discrepancies": [
                {"type": "missing_document", "severity": "high", "message": m}
                for m in missing_items
            ] + discrepancies if has_discrepancies else [],
            "is_complete": is_complete,
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

    def _run_single_validation(self, document, extracted_data: dict) -> dict:
        """Run validation rules on a single document using the integrity gate."""
        issues: list[str] = []
        errors: list[str] = []

        # Check file-level integrity
        if document.file_size_bytes is not None and document.file_size_bytes == 0:
            errors.append("File is empty")

        if document.file_hash is None:
            errors.append("Missing file hash")

        # Run deterministic integrity validation on extracted data
        if extracted_data:
            is_valid, integrity_errors = validate_document_integrity(
                extracted_data, document.document_type
            )
            errors.extend(integrity_errors)
            if not is_valid:
                issues.extend(integrity_errors)

        return {
            "document_id": str(document.id),
            "document_type": document.document_type,
            "is_valid": len(errors) == 0,
            "issues": issues,
            "errors": errors,
            "extracted_data": extracted_data,
        }

    def _check_cross_document_consistency(self, extracted_data_by_type: dict[str, dict]) -> list[dict]:
        """Check cross-document consistency for identity, income, and address."""
        discrepancies: list[dict] = []

        # Income consistency: compare bank statement, application form, and credit report
        bank_data = extracted_data_by_type.get("bank_statement", {})
        app_form_data = extracted_data_by_type.get("application_form", {})
        credit_data = extracted_data_by_type.get("credit_report", {})

        if bank_data and app_form_data:
            bank_balance = bank_data.get("closing_balance")
            app_income = app_form_data.get("total_monthly_income")

            if bank_balance is not None and app_income is not None:
                try:
                    bank_val = Decimal(str(bank_balance))
                    income_val = Decimal(str(app_income))
                    # If average balance is less than monthly income, flag it
                    if bank_val < income_val * Decimal("0.5") and bank_val < Decimal("1000"):
                        msg = (
                            f"Bank balance ({bank_val}) is unusually low compared to "
                            f"declared monthly income ({income_val})"
                        )
                        discrepancies.append({
                            "type": "income_inconsistency",
                            "severity": "medium",
                            "message": msg,
                        })
                        logger.debug("income_check_failed", severity="medium", message=msg)
                except Exception:
                    pass

        # Check debt-to-income from credit report vs application
        if credit_data and app_form_data:
            total_outstanding = credit_data.get("total_outstanding_balance")
            monthly_income = app_form_data.get("total_monthly_income")

            if total_outstanding and monthly_income:
                try:
                    debt = Decimal(str(total_outstanding))
                    income = Decimal(str(monthly_income))
                    if income > 0:
                        dti_ratio = debt / income
                        if dti_ratio > Decimal("10"):  # Debt > 10x monthly income
                            msg = (
                                f"Debt-to-income ratio is {dti_ratio:.1f}x "
                                f"(outstanding: {debt}, monthly income: {income})"
                            )
                            discrepancies.append({
                                "type": "high_debt_to_income",
                                "severity": "high",
                                "message": msg,
                            })
                            logger.debug("debt_to_income_check_failed", dti_ratio=float(dti_ratio), severity="high")
                except Exception:
                    pass

        # Address consistency check
        eid_data = extracted_data_by_type.get("emirates_id", {})
        if eid_data and app_form_data:
            eid_address = eid_data.get("address")
            app_address = app_form_data.get("address")
            if eid_address and app_address:
                eid_emirate = str(eid_address).lower() if isinstance(eid_address, str) else str(eid_address)
                app_emirate = str(app_address).lower() if isinstance(app_address, str) else str(app_address)
                # Simple check - in production would use more sophisticated matching
                if eid_emirate and app_emirate and "abudhabi" not in eid_emirate and "dubai" not in eid_emirate:
                    if eid_emirate != app_emirate and len(eid_emirate) > 2 and len(app_emirate) > 2:
                        msg = f"Address mismatch: Emirates ID ({eid_address}) vs Application ({app_address})"
                        discrepancies.append({
                            "type": "address_inconsistency",
                            "severity": "low",
                            "message": msg,
                        })
                        logger.debug("address_check_failed", severity="low", message=msg)

        return discrepancies

    def _get_required_documents(self, support_category: str | None) -> list[str]:
        """Get list of required documents for a support category."""
        required = {
            "divorced": ["emirates_id", "bank_statement", "credit_report", "application_form"],
            "abandoned": ["emirates_id", "bank_statement", "credit_report", "application_form"],
            "unknown_parentage": ["emirates_id", "bank_statement", "application_form"],
            "health_disability": ["emirates_id", "bank_statement", "credit_report", "application_form", "resume"],
        }
        if support_category is None:
            return ["emirates_id", "bank_statement", "credit_report", "application_form"]
        return required.get(support_category.lower(), ["emirates_id", "bank_statement", "credit_report", "application_form"])

    async def _fetch_extracted_data(self, document) -> dict:
        """Fetch extracted data for a document from the appropriate repository."""
        repo_map = {
            "emirates_id": self.emirates_id_repo,
            "bank_statement": self.bank_stmt_repo,
            "credit_report": self.credit_report_repo,
            "resume": self.resume_repo,
            "assets_liabilities": self.assets_liabilities_repo,
            "application_form": self.application_form_repo,
        }
        repo = repo_map.get(document.document_type)
        if repo is None:
            return {}

        extracted = await repo.get_by_document_id(document.id)
        if extracted is None:
            return {}

        # Convert ORM model to dict
        data = {}
        for col in extracted.__table__.columns:
            val = getattr(extracted, col.name, None)
            if val is not None:
                data[col.name] = val
        return data

    async def _fetch_all_extracted_data(self, documents: list) -> dict[str, dict]:
        """Fetch extracted data for all documents, keyed by document type."""
        result = {}
        for doc in documents:
            data = await self._fetch_extracted_data(doc)
            if data:
                result[doc.document_type] = data
        return result
