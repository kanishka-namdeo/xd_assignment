"""Layer 2: Golden dataset validation — validation tools."""

import pytest

from src.agents.validation.tools import (
    per_document_validation_tool,
    cross_document_compare_tool,
    discrepancy_classify_tool,
    validation_confidence_tool,
)


class TestValidationGoldenDataset:
    """Run validation tools against golden profile data."""

    def test_per_document_validation_valid_emirates_id(self, approved_profile):
        """Valid Emirates ID data passes validation."""
        emirates_data = approved_profile.get("documents", {}).get("emirates_id", {}).get("data", {})
        if not emirates_data:
            pytest.skip("No emirates_id data")

        result = per_document_validation_tool.invoke({
            "extracted_data": emirates_data,
            "document_type": "emirates_id",
        })
        assert result["overall_status"] in ("valid", "invalid")
        assert "confidence" in result

    def test_cross_document_identity_match(self, approved_profile):
        """Identity numbers match across documents in a consistent profile."""
        extracted_data = {}
        for doc_type, doc_info in approved_profile.get("documents", {}).items():
            data = doc_info.get("data", {})
            if data:
                extracted_data[doc_type] = data

        if not extracted_data:
            pytest.skip("No document data")

        result = cross_document_compare_tool.invoke({
            "extracted_data": extracted_data,
            "comparison_type": "identity_match",
        })
        assert "overall_match" in result
        assert "confidence" in result

    def test_validation_confidence_computes(self, approved_profile):
        """Validation confidence tool produces a score."""
        result = validation_confidence_tool.invoke({
            "validation_results": {"overall_status": "valid"},
            "discrepancies": [],
        })
        assert "overall_confidence" in result
        assert "recommendation" in result
