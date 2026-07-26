"""Extraction output schema."""

from pydantic import BaseModel, Field


class ExtractionOutput(BaseModel):
    """Structured output from the extraction agent.

    This model validates and structures the JSON output from the ReAct agent,
    providing type safety and clear error messages when parsing fails.
    """

    document_type: str = Field(..., description="Type of document extracted")
    extraction_confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence score",
    )
    # Allow additional fields dynamically
    model_config = {"extra": "allow"}
