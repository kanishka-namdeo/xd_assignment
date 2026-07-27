"""Layer 2: Golden dataset validation — extraction tools."""

import pytest
from pathlib import Path

from src.agents.extraction.tools import (
    ocr_extract_tool,
    pdf_parse_tool,
    confidence_score_tool,
)

EVALS_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "test_applicants"


class TestExtractionGoldenDataset:
    """Run extraction tools against real documents and validate against ground truth."""

    def test_ocr_extract_emirates_id(self, approved_profile):
        """OCR tool extracts text from Emirates ID image."""
        pytest.importorskip("paddleocr")
        doc_files = approved_profile.get("documents", {}).get("emirates_id", {}).get("files", [])
        if not doc_files:
            pytest.skip("No emirates_id files in profile")

        front_file = doc_files[0]
        file_path = EVALS_DATA_DIR / approved_profile["profile_name"] / front_file
        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        result = ocr_extract_tool.invoke({"file_path": str(file_path)})
        assert "error" not in result
        assert "text" in result or "blocks" in result
        assert result.get("confidence", 0) > 0

    def test_pdf_parse_bank_statement(self, approved_profile):
        """PDF parse tool extracts bank statement data."""
        pytest.importorskip("pymupdf4llm")
        doc_files = approved_profile.get("documents", {}).get("bank_statement", {}).get("files", [])
        if not doc_files:
            pytest.skip("No bank_statement files in profile")

        file_path = EVALS_DATA_DIR / approved_profile["profile_name"] / doc_files[0]
        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        result = pdf_parse_tool.invoke({"file_path": str(file_path)})
        assert "error" not in result
        assert "markdown" in result or "json_structure" in result

    def test_confidence_score_computes(self, approved_profile):
        """Confidence score tool computes scores for extracted data."""
        emirates_data = approved_profile.get("documents", {}).get("emirates_id", {}).get("data", {})
        if not emirates_data:
            pytest.skip("No emirates_id data in profile")

        result = confidence_score_tool.invoke({
            "extracted_data": emirates_data,
            "document_type": "emirates_id",
        })
        assert "error" not in result or result.get("overall_confidence") >= 0
