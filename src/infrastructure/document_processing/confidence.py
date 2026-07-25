"""Confidence scoring for document extraction."""

from typing import Any

import structlog
from pydantic import BaseModel, Field

from .schemas import (
    ApplicationFormExtracted,
    AssetsLiabilitiesExtracted,
    BankStatementExtracted,
    CreditReportExtracted,
    EmiratesIDExtracted,
    ResumeExtracted,
)

logger = structlog.get_logger(__name__)


class ConfidenceScore(BaseModel):
    """Confidence score with routing decision."""

    overall_confidence: float = Field(ge=0.0, le=1.0)
    routing_decision: str = Field(pattern="^(auto|spot_check|manual_review)$")
    field_confidences: dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: list[str] = Field(default_factory=list)


class ConfidenceScorer:
    """Compute confidence scores and routing decisions.
    
    Provides field-level confidence scores and overall document confidence.
    Routes documents based on confidence thresholds:
    - >0.95: Auto-process
    - 0.80-0.95: Spot-check
    - <0.80: Manual review
    """

    # Confidence thresholds
    AUTO_THRESHOLD = 0.95
    MANUAL_THRESHOLD = 0.80

    def compute_confidence(
        self,
        extracted_data: BaseModel,
        raw_extraction_confidence: float | None = None,
    ) -> ConfidenceScore:
        """Compute confidence score for extracted data.
        
        Args:
            extracted_data: Pydantic model with extracted data
            raw_extraction_confidence: Confidence from extraction process
            
        Returns:
            ConfidenceScore with routing decision
            
        Example:
            >>> scorer = ConfidenceScorer()
            >>> score = scorer.compute_confidence(emirates_id_data)
            >>> print(score.routing_decision)  # "auto", "spot_check", or "manual_review"
        """
        field_confidences: dict[str, float] = {}
        
        # Compute field-level confidences based on data type
        if isinstance(extracted_data, EmiratesIDExtracted):
            field_confidences = self._score_emirates_id(extracted_data)
        elif isinstance(extracted_data, BankStatementExtracted):
            field_confidences = self._score_bank_statement(extracted_data)
        elif isinstance(extracted_data, CreditReportExtracted):
            field_confidences = self._score_credit_report(extracted_data)
        elif isinstance(extracted_data, ResumeExtracted):
            field_confidences = self._score_resume(extracted_data)
        elif isinstance(extracted_data, AssetsLiabilitiesExtracted):
            field_confidences = self._score_assets_liabilities(extracted_data)
        elif isinstance(extracted_data, ApplicationFormExtracted):
            field_confidences = self._score_application_form(extracted_data)
        else:
            # Generic scoring
            field_confidences = {"default": raw_extraction_confidence or 0.5}

        # Calculate overall confidence (weighted average)
        if field_confidences:
            overall = sum(field_confidences.values()) / len(field_confidences)
        else:
            overall = raw_extraction_confidence or 0.5

        # Blend with raw extraction confidence if available
        if raw_extraction_confidence is not None:
            overall = (overall * 0.7) + (raw_extraction_confidence * 0.3)

        # Find low confidence fields
        low_confidence_fields = [
            field
            for field, conf in field_confidences.items()
            if conf < self.MANUAL_THRESHOLD
        ]

        # Determine routing decision
        if overall >= self.AUTO_THRESHOLD:
            routing = "auto"
        elif overall >= self.MANUAL_THRESHOLD:
            routing = "spot_check"
        else:
            routing = "manual_review"

        self.logger.info(
            "confidence_scored",
            document_type=type(extracted_data).__name__,
            overall_confidence=round(overall, 4),
            routing_decision=routing,
            field_count=len(field_confidences),
            low_confidence_count=len(low_confidence_fields),
            low_confidence_fields=low_confidence_fields if low_confidence_fields else None,
        )

        return ConfidenceScore(
            overall_confidence=overall,
            routing_decision=routing,
            field_confidences=field_confidences,
            low_confidence_fields=low_confidence_fields,
        )

    def _score_emirates_id(self, data: EmiratesIDExtracted) -> dict[str, float]:
        """Score Emirates ID extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["identity_number"] = 0.98 if data.identity_number else 0.0
        scores["full_name_en"] = 0.95 if data.full_name_en else 0.0
        scores["nationality"] = 0.95 if data.nationality else 0.0
        scores["date_of_birth"] = 0.95 if data.date_of_birth else 0.0
        scores["gender"] = 0.95 if data.gender else 0.0
        scores["expiry_date"] = 0.95 if data.expiry_date else 0.0
        
        # Optional fields
        scores["full_name_ar"] = 0.90 if data.full_name_ar else 0.70
        scores["card_number"] = 0.90 if data.card_number else 0.70
        scores["occupation"] = 0.85 if data.occupation else 0.70
        scores["employer_name"] = 0.85 if data.employer_name else 0.70
        
        # MRZ verification boost
        if data.is_mrz_verified:
            for key in ["identity_number", "full_name_en", "date_of_birth"]:
                scores[key] = min(1.0, scores[key] + 0.02)
        
        return scores

    def _score_bank_statement(self, data: BankStatementExtracted) -> dict[str, float]:
        """Score bank statement extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["bank_name"] = 0.95 if data.bank_name else 0.0
        scores["account_holder_name"] = 0.95 if data.account_holder_name else 0.0
        scores["account_number"] = 0.95 if data.account_number else 0.0
        scores["opening_balance"] = 0.95 if data.opening_balance is not None else 0.0
        scores["closing_balance"] = 0.95 if data.closing_balance is not None else 0.0
        
        # Transactions
        scores["transactions"] = 0.90 if data.transaction_count > 0 else 0.50
        
        # Balance reconciliation
        if data.is_balance_reconciled:
            scores["balance_reconciliation"] = 0.98
        else:
            scores["balance_reconciliation"] = 0.70
        
        # Optional fields
        scores["iban"] = 0.90 if data.iban else 0.70
        scores["account_type"] = 0.85 if data.account_type else 0.70
        
        return scores

    def _score_credit_report(self, data: CreditReportExtracted) -> dict[str, float]:
        """Score credit report extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["cb_subject_id"] = 0.95 if data.cb_subject_id else 0.0
        scores["identity_number"] = 0.95 if data.identity_number else 0.0
        scores["full_name"] = 0.95 if data.full_name else 0.0
        scores["credit_score"] = 0.95 if data.credit_score else 0.0
        scores["risk_band"] = 0.95 if data.risk_band else 0.0
        
        # Account counts
        scores["total_active_accounts"] = 0.90
        scores["total_closed_accounts"] = 0.90
        
        # Financial data
        scores["total_outstanding_balance"] = 0.90 if data.total_outstanding_balance else 0.0
        
        # Facilities
        scores["active_facilities"] = 0.85 if data.active_facilities else 0.70
        
        # Payment history
        scores["late_payment_count"] = 0.90
        scores["defaulted_accounts"] = 0.90
        
        return scores

    def _score_resume(self, data: ResumeExtracted) -> dict[str, float]:
        """Score resume extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["full_name"] = 0.95 if data.full_name else 0.0
        
        # Contact info
        scores["email"] = 0.90 if data.email else 0.60
        scores["phone"] = 0.90 if data.phone else 0.60
        
        # Work experience
        scores["work_experience"] = 0.90 if data.total_positions > 0 else 0.50
        
        # Education
        scores["education"] = 0.85 if data.education else 0.60
        
        # Skills
        scores["skills"] = 0.85 if data.skill_count > 0 else 0.50
        
        return scores

    def _score_assets_liabilities(self, data: AssetsLiabilitiesExtracted) -> dict[str, float]:
        """Score assets/liabilities extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["applicant_name"] = 0.95 if data.applicant_name else 0.0
        scores["statement_date"] = 0.95 if data.statement_date else 0.0
        scores["total_assets"] = 0.95 if data.total_assets is not None else 0.0
        scores["total_liabilities"] = 0.95 if data.total_liabilities is not None else 0.0
        scores["net_worth"] = 0.95 if data.net_worth is not None else 0.0
        
        # Asset categories
        scores["asset_details"] = 0.85 if data.asset_details else 0.70
        
        # Liability categories
        scores["liability_details"] = 0.85 if data.liability_details else 0.70
        
        return scores

    def _score_application_form(self, data: ApplicationFormExtracted) -> dict[str, float]:
        """Score application form extraction confidence."""
        scores = {}
        
        # Critical fields
        scores["applicant_name"] = 0.95 if data.applicant_name else 0.0
        scores["identity_number"] = 0.95 if data.identity_number else 0.0
        scores["date_of_birth"] = 0.95 if data.date_of_birth else 0.0
        scores["nationality"] = 0.95 if data.nationality else 0.0
        scores["contact_phone"] = 0.95 if data.contact_phone else 0.0
        scores["employment_status"] = 0.95 if data.employment_status else 0.0
        
        # Financial data
        scores["monthly_salary"] = 0.90 if data.monthly_salary is not None else 0.60
        scores["total_monthly_income"] = 0.90 if data.total_monthly_income else 0.0
        
        # Optional fields
        scores["contact_email"] = 0.85 if data.contact_email else 0.60
        scores["employer_name"] = 0.85 if data.employer_name else 0.60
        scores["support_category"] = 0.85 if data.support_category else 0.60
        
        # Declaration
        scores["declaration_signed"] = 0.95 if data.is_declaration_signed else 0.70
        
        return scores
