"""Eligibility service - compute eligibility scores using ML models."""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.db.repositories.extraction_repo import (
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
)

logger = structlog.get_logger()


class EligibilityService:
    """Compute and manage eligibility scores for applications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.application_repo = ApplicationRepository(session)
        self.document_repo = DocumentRepository(session)
        self.emirates_id_repo = EmiratesIDRepository(session)
        self.bank_stmt_repo = BankStatementRepository(session)
        self.credit_report_repo = CreditReportRepository(session)

    async def compute_eligibility(self, application_id: UUID) -> dict:
        """Compute eligibility score for an application using extracted data."""
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise ValueError(f"Application {application_id} not found")

        features = await self._extract_features(application.applicant_id)

        score, factors = self._compute_score(features)

        application.eligibility_score = score
        application.eligibility_factors = factors
        await self.application_repo.update(application)

        logger.info(
            "eligibility_computed",
            application_id=str(application_id),
            score=score,
        )
        return {
            "application_id": str(application_id),
            "eligibility_score": score,
            "factors": factors,
            "features_used": list(features.keys()),
        }

    async def get_eligibility(self, application_id: UUID) -> dict | None:
        """Retrieve stored eligibility results."""
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            return None

        if application.eligibility_score is None:
            return None

        return {
            "application_id": str(application_id),
            "eligibility_score": application.eligibility_score,
            "factors": application.eligibility_factors,
        }

    async def get_eligibility_explanation(self, application_id: UUID) -> str | None:
        """Generate human-readable explanation of eligibility decision."""
        result = await self.get_eligibility(application_id)
        if result is None:
            return None

        score = result["eligibility_score"]
        factors = result.get("factors", {})

        explanation_parts = []
        if score >= 0.7:
            explanation_parts.append("The application meets eligibility criteria.")
        elif score >= 0.5:
            explanation_parts.append("The application is borderline and may require manual review.")
        else:
            explanation_parts.append("The application does not meet minimum eligibility criteria.")

        positive_factors = [k for k, v in factors.items() if v > 0]
        negative_factors = [k for k, v in factors.items() if v < 0]

        if positive_factors:
            explanation_parts.append(f"Positive factors: {', '.join(positive_factors)}.")
        if negative_factors:
            explanation_parts.append(f"Concerns: {', '.join(negative_factors)}.")

        return " ".join(explanation_parts)

    async def _extract_features(self, applicant_id: UUID) -> dict:
        """Extract features from documents for eligibility computation."""
        documents = await self.document_repo.get_by_applicant(applicant_id)
        features = {}

        for doc in documents:
            if doc.document_type == "emirates_id":
                eid_data = await self.emirates_id_repo.get_by_document_id(doc.id)
                if eid_data:
                    features["has_valid_id"] = 1
                    features["id_confidence"] = eid_data.extraction_confidence or 0.0

            elif doc.document_type == "bank_statement":
                bank_data = await self.bank_stmt_repo.get_by_document_id(doc.id)
                if bank_data:
                    features["avg_balance"] = float(bank_data.closing_balance)
                    features["transaction_count"] = bank_data.transaction_count
                    features["bank_confidence"] = bank_data.extraction_confidence or 0.0

            elif doc.document_type == "credit_report":
                credit_data = await self.credit_report_repo.get_by_document_id(doc.id)
                if credit_data:
                    features["credit_score"] = credit_data.credit_score
                    features["credit_utilization"] = float(credit_data.credit_utilization_ratio or 0)
                    features["late_payments"] = credit_data.late_payment_count
                    features["credit_confidence"] = credit_data.extraction_confidence or 0.0

        return features

    def _compute_score(self, features: dict) -> tuple[float, dict]:
        """Compute eligibility score from features.

        Placeholder for ML model (HistGradientBoostingClassifier).
        Returns (score, factor_contributions).
        """
        score = 0.5
        factors = {}

        if features.get("has_valid_id"):
            score += 0.1
            factors["valid_identity"] = 0.1

        credit_score = features.get("credit_score", 600)
        if credit_score >= 700:
            score += 0.2
            factors["good_credit_score"] = 0.2
        elif credit_score < 500:
            score -= 0.2
            factors["poor_credit_score"] = -0.2

        late_payments = features.get("late_payments", 0)
        if late_payments > 3:
            score -= 0.15
            factors["excessive_late_payments"] = -0.15

        avg_balance = features.get("avg_balance", 0)
        if avg_balance > 10000:
            score += 0.1
            factors["healthy_balance"] = 0.1

        score = max(0.0, min(1.0, score))
        return score, factors
