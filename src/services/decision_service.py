"""Decision service - make final application decisions based on eligibility and validation."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.validation_repo import CrossDocumentValidationRepository

logger = structlog.get_logger(__name__)


class DecisionService:
    """Apply decision rules and generate final application outcomes."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.application_repo = ApplicationRepository(session)
        self.validation_repo = CrossDocumentValidationRepository(session)

    async def make_decision(self, application_id: UUID) -> dict:
        """Make final decision for an application."""
        start = datetime.now(timezone.utc)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            logger.warning("application_not_found", application_id=str(application_id))
            raise ValueError(f"Application {application_id} not found")

        eligibility_score = application.eligibility_score
        if eligibility_score is None:
            logger.warning("eligibility_not_computed", application_id=str(application_id))
            raise ValueError(f"Eligibility not computed for application {application_id}")

        validations = await self.validation_repo.get_by_applicant(application.applicant_id)
        unresolved = [v for v in validations if not v.is_resolved]

        decision, explanation = self._apply_decision_rules(
            eligibility_score, unresolved, application.eligibility_factors or {}
        )

        application.decision = decision
        application.decision_explanation = explanation
        await self.application_repo.update(application)

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "decision_made",
            application_id=str(application_id),
            decision=decision,
            eligibility_score=eligibility_score,
            unresolved_issues=len(unresolved),
            duration_ms=round(duration_ms, 2),
        )
        return {
            "application_id": str(application_id),
            "decision": decision,
            "explanation": explanation,
            "eligibility_score": eligibility_score,
            "unresolved_issues": len(unresolved),
        }

    async def persist_decision(
        self,
        application_id: UUID,
        decision: str,
        decision_explanation: str,
        eligibility_score: float,
        eligibility_factors: dict | None = None,
    ) -> None:
        """Persist decision results computed by the orchestrator graph.

        The decision node only produces state updates; this method writes
        them to PostgreSQL so the service layer owns all DB I/O.
        """
        start = datetime.now(timezone.utc)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            logger.warning("application_not_found", application_id=str(application_id))
            return

        application.decision = decision
        application.decision_explanation = decision_explanation
        application.eligibility_score = eligibility_score
        if eligibility_factors is not None:
            application.eligibility_factors = eligibility_factors
        await self.application_repo.update(application)

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "decision_persisted",
            application_id=str(application_id),
            decision=decision,
            eligibility_score=eligibility_score,
            duration_ms=round(duration_ms, 2),
        )

    async def get_decision(self, application_id: UUID) -> dict | None:
        """Retrieve stored decision results."""
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            return None

        if application.decision is None:
            return None

        return {
            "application_id": str(application_id),
            "decision": application.decision,
            "explanation": application.decision_explanation,
            "eligibility_score": application.eligibility_score,
        }

    async def get_decision_explanation(self, application_id: UUID) -> str | None:
        """Get human-readable decision explanation."""
        result = await self.get_decision(application_id)
        if result is None:
            return None
        return result.get("explanation")

    def _apply_decision_rules(
        self,
        eligibility_score: float,
        unresolved_validations: list,
        factors: dict,
    ) -> tuple[str, str]:
        """Apply decision rules to determine application outcome.

        Rules:
        - score >= 0.7 and no critical issues -> approved
        - score >= 0.5 or minor issues -> manual_review
        - score < 0.5 or critical issues -> soft_decline
        """
        has_critical_issues = any(
            v.status == "discrepancies_found" and v.confidence_score < 0.5
            for v in unresolved_validations
        )

        if eligibility_score >= 0.7 and not has_critical_issues:
            decision = "approved"
            explanation = (
                f"Application approved with eligibility score {eligibility_score:.2f}. "
                "All validation checks passed."
            )
        elif eligibility_score >= 0.5 or (
            len(unresolved_validations) > 0 and not has_critical_issues
        ):
            decision = "manual_review"
            explanation = (
                f"Application requires manual review. Eligibility score: {eligibility_score:.2f}. "
                f"Unresolved validation issues: {len(unresolved_validations)}."
            )
        else:
            decision = "soft_decline"
            explanation = (
                f"Application declined with eligibility score {eligibility_score:.2f}. "
            )
            if has_critical_issues:
                explanation += "Critical validation issues detected."

        logger.debug(
            "decision_rule_evaluated",
            eligibility_score=eligibility_score,
            decision=decision,
            has_critical_issues=has_critical_issues,
            unresolved_count=len(unresolved_validations),
        )

        if has_critical_issues:
            logger.warning(
                "unresolved_validation_issues",
                unresolved_count=len(unresolved_validations),
                critical_issues=has_critical_issues,
            )

        return decision, explanation
