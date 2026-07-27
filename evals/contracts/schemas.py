"""Pydantic contract definitions for all agent tool outputs."""

from pydantic import BaseModel, ConfigDict


class BaseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ExtractionOutputContract(BaseContract):
    """Contract for extraction tool outputs."""
    duration_ms: float
    error: str | None = None


class OcrExtractContract(ExtractionOutputContract):
    text: str | None = None
    blocks: list | None = None
    confidence: float | None = None
    language: str | None = None


class PdfParseContract(ExtractionOutputContract):
    markdown: str | None = None
    json_structure: dict | None = None
    confidence: float | None = None
    field_count: int | None = None
    document_type: str | None = None


class TableExtractContract(ExtractionOutputContract):
    tables: list | None = None
    table_count: int | None = None
    confidence: float | None = None
    flavor: str | None = None


class ResumeParseContract(ExtractionOutputContract):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    total_positions: int | None = None
    confidence: float | None = None


class XlsxExtractContract(ExtractionOutputContract):
    sheets: dict | None = None
    sheet_count: int | None = None
    sheet_names: list | None = None


class ConfidenceScoreContract(ExtractionOutputContract):
    overall_confidence: float | None = None
    routing_decision: str | None = None
    field_confidences: dict | None = None
    low_confidence_fields: list | None = None


class ValidationOutputContract(BaseContract):
    duration_ms: float
    confidence: float


class PerDocumentValidationContract(ValidationOutputContract):
    document_type: str
    validation_results: list
    overall_status: str
    errors: list


class CrossDocumentCompareContract(ValidationOutputContract):
    comparison_type: str
    overall_match: bool
    discrepancies: list


class DiscrepancyClassifyContract(ValidationOutputContract):
    discrepancy_type: str
    classification: str
    recommended_action: str


class ApplicantClarifyContract(ValidationOutputContract):
    question: str
    field: str
    discrepancy_type: str
    priority: str


class ValidationConfidenceContract(ValidationOutputContract):
    overall_confidence: float
    recommendation: str
    unresolved_count: int
    critical_count: int


class EligibilityOutputContract(BaseContract):
    duration_ms: float
    predicted_class: str | None = None
    probability: float | None = None
    method: str | None = None


class MlPredictContract(EligibilityOutputContract):
    factor_contributions: dict | None = None


class FeatureImportanceContract(EligibilityOutputContract):
    top_features: list | None = None


class AdjustFactorContract(BaseContract):
    duration_ms: float
    adjusted_score: float
    adjustment_amount: float
    reasoning: str


class EligibilityExplanationContract(BaseContract):
    duration_ms: float
    explanation: str
    key_factors: list
    recommendation: str


class DecisionOutputContract(BaseContract):
    duration_ms: float


class DecisionLogicContract(DecisionOutputContract):
    decision: str
    reasoning: str
    eligibility_score: float
    validation_confidence: float
    critical_discrepancies: int


class DecisionExplanationContract(DecisionOutputContract):
    explanation: str
    key_factors: list
    support_category: str


class EnablementRecommendationContract(DecisionOutputContract):
    recommendations: list
    total_count: int


class DecisionFormattingContract(DecisionOutputContract):
    title: str
    decision: str
    color: str
    icon: str
    explanation: str
    next_steps: list


CONTRACT_MAP = {
    "ocr_extract_tool": OcrExtractContract,
    "pdf_parse_tool": PdfParseContract,
    "table_extract_tool": TableExtractContract,
    "resume_parse_tool": ResumeParseContract,
    "xlsx_extract_tool": XlsxExtractContract,
    "confidence_score_tool": ConfidenceScoreContract,
    "per_document_validation_tool": PerDocumentValidationContract,
    "cross_document_compare_tool": CrossDocumentCompareContract,
    "discrepancy_classify_tool": DiscrepancyClassifyContract,
    "applicant_clarify_tool": ApplicantClarifyContract,
    "validation_confidence_tool": ValidationConfidenceContract,
    "ml_model_predict_tool": MlPredictContract,
    "feature_importance_tool": FeatureImportanceContract,
    "adjust_factor_weighting_tool": AdjustFactorContract,
    "eligibility_explanation_tool": EligibilityExplanationContract,
    "decision_logic_tool": DecisionLogicContract,
    "decision_explanation_tool": DecisionExplanationContract,
    "enablement_recommendation_tool": EnablementRecommendationContract,
    "decision_formatting_tool": DecisionFormattingContract,
}
