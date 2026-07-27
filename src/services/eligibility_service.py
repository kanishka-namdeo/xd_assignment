"""Eligibility service - compute eligibility scores using rule-based scoring."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from langfuse import observe
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.constants.eligibility_rules import CATEGORY_ADJUSTMENTS
from src.infrastructure.db.repositories.application_repo import ApplicationRepository
from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.db.repositories.extraction_repo import (
    ApplicationFormRepository,
    AssetsLiabilitiesRepository,
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
    ResumeRepository,
)

logger = structlog.get_logger(__name__)


class EligibilityService:
    """Compute and manage eligibility scores for applications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.application_repo = ApplicationRepository(session)
        self.document_repo = DocumentRepository(session)
        self.emirates_id_repo = EmiratesIDRepository(session)
        self.bank_stmt_repo = BankStatementRepository(session)
        self.credit_report_repo = CreditReportRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.assets_liabilities_repo = AssetsLiabilitiesRepository(session)
        self.application_form_repo = ApplicationFormRepository(session)

    @observe(as_type="generation", name="compute_eligibility")
    async def compute_eligibility(self, application_id: UUID) -> dict:
        """Compute eligibility score for an application using extracted data."""
        start = datetime.now(timezone.utc)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            logger.warning("application_not_found", application_id=str(application_id))
            raise ValueError(f"Application {application_id} not found")

        features = await self._extract_features(application.applicant_id)

        score, factors = self._compute_score(features)

        application.eligibility_score = score
        application.eligibility_factors = factors
        await self.application_repo.update(application)

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "eligibility_computed",
            application_id=str(application_id),
            score=score,
            positive_factors=[k for k, v in factors.items() if v > 0],
            negative_factors=[k for k, v in factors.items() if v < 0],
            duration_ms=round(duration_ms, 2),
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
        features = await self._extract_features_for_explanation(application_id)

        explanation_parts = []

        # Overall eligibility statement
        if score >= 0.7:
            explanation_parts.append(
                f"The application meets eligibility criteria with a score of {score:.0%}."
            )
        elif score >= 0.5:
            explanation_parts.append(
                f"The application is borderline with a score of {score:.0%} and may require manual review."
            )
        else:
            explanation_parts.append(
                f"The application does not meet minimum eligibility criteria with a score of {score:.0%}."
            )

        # Support category
        support_category = features.get("support_category", "unknown")
        if support_category:
            adjustment = CATEGORY_ADJUSTMENTS.get(support_category, 0)
            explanation_parts.append(
                f"Support category: {support_category.replace('_', ' ').title()} "
                f"(+{adjustment:.0%} adjustment applied)."
            )

        # Credit assessment
        credit_score = features.get("credit_score", 0)
        if credit_score >= 700:
            explanation_parts.append(
                f"Credit score of {credit_score} is in the good range, positively impacting eligibility."
            )
        elif credit_score >= 500:
            explanation_parts.append(
                f"Credit score of {credit_score} is in the fair range."
            )
        else:
            explanation_parts.append(
                f"Credit score of {credit_score} is below the preferred threshold."
            )

        # Debt-to-income
        dti = features.get("debt_to_income_ratio", 0)
        if dti is not None and dti > 0:
            if dti < 0.5:
                explanation_parts.append(
                    f"Debt-to-income ratio of {dti:.0%} is healthy."
                )
            elif dti < 0.8:
                explanation_parts.append(
                    f"Debt-to-income ratio of {dti:.0%} is moderate."
                )
            else:
                explanation_parts.append(
                    f"Debt-to-income ratio of {dti:.0%} is high and may be a concern."
                )

        # Employment stability
        employment_months = features.get("employment_stability_months", 0)
        if employment_months >= 24:
            explanation_parts.append(
                f"Employment stability of {employment_months} months demonstrates consistent income."
            )
        elif employment_months >= 12:
            explanation_parts.append(
                f"Employment history of {employment_months} months is adequate."
            )
        else:
            explanation_parts.append(
                f"Employment history of {employment_months} months is relatively short."
            )

        # Family size
        family_size = features.get("family_size", 0)
        if family_size > 0:
            explanation_parts.append(
                f"Family size of {family_size} members was considered in the assessment."
            )

        # Housing cost ratio
        housing_ratio = features.get("housing_cost_ratio", 0)
        if housing_ratio > 0:
            if housing_ratio <= 0.3:
                explanation_parts.append(
                    f"Housing cost ratio of {housing_ratio:.0%} is within acceptable limits."
                )
            else:
                explanation_parts.append(
                    f"Housing cost ratio of {housing_ratio:.0%} exceeds the recommended 30% threshold."
                )

        # Positive and negative factors
        positive_factors = [k for k, v in factors.items() if v > 0]
        negative_factors = [k for k, v in factors.items() if v < 0]

        if positive_factors:
            explanation_parts.append(f"Positive factors: {', '.join(positive_factors)}.")
        if negative_factors:
            explanation_parts.append(f"Concerns: {', '.join(negative_factors)}.")

        return " ".join(explanation_parts)

    async def _extract_features(self, applicant_id: UUID) -> dict:
        """Extract features from all document types for eligibility computation."""
        documents = await self.document_repo.get_by_applicant(applicant_id)
        features: dict[str, any] = {}
        doc_types_found = []

        for doc in documents:
            if doc.document_type == "emirates_id":
                eid_data = await self.emirates_id_repo.get_by_document_id(doc.id)
                if eid_data:
                    features["has_valid_id"] = 1
                    features["id_confidence"] = eid_data.extraction_confidence or 0.0
                    features["nationality"] = eid_data.nationality
                    doc_types_found.append("emirates_id")

            elif doc.document_type == "bank_statement":
                bank_data = await self.bank_stmt_repo.get_by_document_id(doc.id)
                if bank_data:
                    features["avg_balance"] = float(bank_data.closing_balance or 0)
                    features["transaction_count"] = bank_data.transaction_count or 0
                    features["bank_confidence"] = bank_data.extraction_confidence or 0.0
                    features["opening_balance"] = float(bank_data.opening_balance or 0)
                    features["total_debits"] = float(bank_data.total_debits or 0)
                    features["total_credits"] = float(bank_data.total_credits or 0)
                    doc_types_found.append("bank_statement")

            elif doc.document_type == "credit_report":
                credit_data = await self.credit_report_repo.get_by_document_id(doc.id)
                if credit_data:
                    features["credit_score"] = credit_data.credit_score or 600
                    features["credit_utilization"] = float(credit_data.credit_utilization_ratio or 0)
                    features["late_payments"] = credit_data.late_payment_count or 0
                    features["defaulted_accounts"] = credit_data.defaulted_accounts or 0
                    features["total_outstanding"] = float(credit_data.total_outstanding_balance or 0)
                    features["active_accounts"] = credit_data.total_active_accounts or 0
                    features["credit_confidence"] = credit_data.extraction_confidence or 0.0
                    doc_types_found.append("credit_report")

            elif doc.document_type == "resume":
                resume_data = await self.resume_repo.get_by_document_id(doc.id)
                if resume_data:
                    features["total_positions"] = resume_data.total_positions or 0
                    features["years_of_experience"] = resume_data.years_of_experience or 0
                    features["has_employment"] = 1 if resume_data.total_positions > 0 else 0
                    features["highest_degree"] = resume_data.highest_degree
                    features["resume_confidence"] = resume_data.extraction_confidence or 0.0

                    # Calculate employment stability from work experience
                    work_exp = resume_data.work_experience or {}
                    if isinstance(work_exp, list) and work_exp:
                        total_months = 0
                        for exp in work_exp:
                            if isinstance(exp, dict):
                                duration = exp.get("duration_months", 0)
                                if duration:
                                    total_months += duration
                        features["employment_stability_months"] = total_months
                    elif isinstance(work_exp, dict):
                        # Handle JSONB dict format
                        positions = work_exp.get("positions", [])
                        if isinstance(positions, list):
                            total_months = sum(p.get("duration_months", 0) for p in positions)
                            features["employment_stability_months"] = total_months
                    doc_types_found.append("resume")

            elif doc.document_type == "assets_liabilities":
                assets_data = await self.assets_liabilities_repo.get_by_document_id(doc.id)
                if assets_data:
                    features["total_assets"] = float(assets_data.total_assets or 0)
                    features["total_liabilities"] = float(assets_data.total_liabilities or 0)
                    features["net_worth"] = float(assets_data.net_worth or 0)
                    features["monthly_income_from_assets"] = float(assets_data.monthly_income or 0)
                    doc_types_found.append("assets_liabilities")

            elif doc.document_type == "application_form":
                form_data = await self.application_form_repo.get_by_document_id(doc.id)
                if form_data:
                    features["monthly_salary"] = float(form_data.monthly_salary or 0)
                    features["other_income"] = float(form_data.other_income or 0)
                    features["total_monthly_income"] = float(form_data.total_monthly_income or 0)
                    features["family_size"] = form_data.family_size or 1
                    features["support_category"] = form_data.support_category
                    features["employment_status"] = form_data.employment_status
                    features["housing_status"] = form_data.housing_status
                    features["monthly_rent"] = float(form_data.monthly_rent or 0)
                    features["monthly_mortgage"] = float(form_data.monthly_mortgage or 0)
                    features["form_confidence"] = form_data.extraction_confidence or 0.0
                    doc_types_found.append("application_form")

        logger.debug(
            "feature_extraction_summary",
            applicant_id=str(applicant_id),
            documents_processed=len(doc_types_found),
            document_types=doc_types_found,
            features_extracted=len(features),
        )

        # Calculate derived features
        features = self._calculate_derived_features(features)

        logger.debug(
            "derived_features_calculated",
            applicant_id=str(applicant_id),
            debt_to_income_ratio=features.get("debt_to_income_ratio"),
            housing_cost_ratio=features.get("housing_cost_ratio"),
            credit_health=features.get("credit_health"),
            employment_stability_months=features.get("employment_stability_months"),
        )

        return features

    def _calculate_derived_features(self, features: dict) -> dict:
        """Calculate derived features from raw extracted data."""
        # Monthly income
        monthly_income = features.get("total_monthly_income", 0)
        if monthly_income == 0:
            monthly_income = features.get("monthly_salary", 0) + features.get("other_income", 0)
            features["total_monthly_income"] = monthly_income

        # Debt-to-income ratio
        total_outstanding = features.get("total_outstanding", 0)
        if monthly_income > 0:
            features["debt_to_income_ratio"] = total_outstanding / monthly_income
        else:
            features["debt_to_income_ratio"] = 0

        # Housing cost ratio
        housing_cost = features.get("monthly_rent", 0) + features.get("monthly_mortgage", 0)
        if monthly_income > 0:
            features["housing_cost_ratio"] = housing_cost / monthly_income
        else:
            features["housing_cost_ratio"] = 0

        # Employment stability default
        if "employment_stability_months" not in features:
            years_exp = features.get("years_of_experience", 0)
            if years_exp:
                features["employment_stability_months"] = years_exp * 12
            else:
                features["employment_stability_months"] = 0

        # Credit health score
        credit_score = features.get("credit_score", 600)
        if credit_score >= 750:
            features["credit_health"] = "excellent"
        elif credit_score >= 700:
            features["credit_health"] = "good"
        elif credit_score >= 650:
            features["credit_health"] = "fair"
        else:
            features["credit_health"] = "poor"

        return features

    async def _extract_features_for_explanation(self, applicant_id: UUID) -> dict:
        """Extract key features needed for generating the explanation."""
        features = await self._extract_features(applicant_id)
        return features

    def _compute_score(self, features: dict) -> tuple[float, dict]:
        """Compute eligibility score from features using rule-based scoring.

        Returns (score, factor_contributions).
        """
        score = 0.4  # Base score
        factors: dict[str, float] = {}

        # Identity verification (+0.10)
        if features.get("has_valid_id"):
            score += 0.10
            factors["valid_identity"] = 0.10

        # Credit score assessment
        credit_score = features.get("credit_score", 600)
        if credit_score >= 750:
            score += 0.20
            factors["excellent_credit"] = 0.20
        elif credit_score >= 700:
            score += 0.15
            factors["good_credit"] = 0.15
        elif credit_score >= 650:
            score += 0.08
            factors["fair_credit"] = 0.08
        elif credit_score >= 500:
            score += 0.0
            factors["poor_credit"] = 0.0
        else:
            score -= 0.10
            factors["very_poor_credit"] = -0.10

        # Late payments penalty
        late_payments = features.get("late_payments", 0)
        if late_payments == 0:
            score += 0.05
            factors["clean_payment_history"] = 0.05
        elif late_payments <= 2:
            score -= 0.05
            factors["minor_payment_issues"] = -0.05
        else:
            score -= 0.15
            factors["excessive_late_payments"] = -0.15

        # Defaulted accounts penalty
        defaulted = features.get("defaulted_accounts", 0)
        if defaulted > 0:
            score -= 0.20
            factors["defaulted_accounts"] = -0.20

        # Financial stability - average balance
        avg_balance = features.get("avg_balance", 0)
        monthly_income = features.get("total_monthly_income", 0)
        if monthly_income > 0 and avg_balance >= monthly_income * 3:
            score += 0.10
            factors["healthy_savings"] = 0.10
        elif avg_balance > 5000:
            score += 0.05
            factors["adequate_savings"] = 0.05

        # Debt-to-income ratio
        dti = features.get("debt_to_income_ratio", 0)
        if dti < 0.3:
            score += 0.10
            factors["low_debt_ratio"] = 0.10
        elif dti < 0.5:
            score += 0.05
            factors["moderate_debt_ratio"] = 0.05
        elif dti < 0.8:
            score -= 0.05
            factors["high_debt_ratio"] = -0.05
        else:
            score -= 0.15
            factors["excessive_debt_ratio"] = -0.15

        # Employment stability
        employment_months = features.get("employment_stability_months", 0)
        if employment_months >= 24:
            score += 0.10
            factors["stable_employment"] = 0.10
        elif employment_months >= 12:
            score += 0.05
            factors["adequate_employment"] = 0.05
        else:
            score -= 0.05
            factors["short_employment_history"] = -0.05

        # Net worth
        net_worth = features.get("net_worth", 0)
        if net_worth > 500000:
            score += 0.08
            factors["strong_net_worth"] = 0.08
        elif net_worth > 100000:
            score += 0.04
            factors["positive_net_worth"] = 0.04
        elif net_worth < 0:
            score -= 0.10
            factors["negative_net_worth"] = -0.10

        # Support category adjustment
        support_category = features.get("support_category", "")
        category_adjustment = CATEGORY_ADJUSTMENTS.get(support_category, 0)
        if category_adjustment > 0:
            score += category_adjustment
            factors[f"{support_category}_adjustment"] = category_adjustment

        # Family size consideration
        family_size = features.get("family_size", 1)
        if family_size > 3:
            score += 0.05
            factors["large_family_support"] = 0.05

        # Housing cost ratio
        housing_ratio = features.get("housing_cost_ratio", 0)
        if housing_ratio <= 0.25:
            score += 0.05
            factors["affordable_housing"] = 0.05
        elif housing_ratio > 0.4:
            score -= 0.05
            factors["high_housing_cost"] = -0.05

        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        logger.debug(
            "score_computation",
            base_score=0.4,
            adjustments=factors,
            final_score=round(score, 4),
        )

        return round(score, 4), factors
