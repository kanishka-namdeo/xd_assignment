"""Unit tests for completeness gate."""

import pytest

from src.agents.gates.completeness import validate_completeness


class TestCompletenessValidation:
    """Test completeness validation."""

    def test_all_documents_present_and_consistent(self):
        """All required documents present with consistent data should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "full_name": "John Doe",
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
                "applicant_name": "John Doe",
                "date_of_birth": "1990-01-01",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            "credit_report": {"status": "valid"},
            "application_form": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert is_complete
        assert len(missing) == 0

    def test_missing_required_document(self):
        """Missing required document should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert any("credit_report" in m for m in missing)
        assert any("application_form" in m for m in missing)

    def test_missing_validation_result(self):
        """Missing validation result should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "full_name": "John Doe",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            # Missing credit_report validation
        }
        required_documents = ["emirates_id", "credit_report"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert any("credit_report" in m and "validated" in m for m in missing)

    def test_identity_mismatch(self):
        """Identity number mismatch across documents should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-9999999-0",  # Different
                "full_name": "John Doe",
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
                "applicant_name": "John Doe",
                "date_of_birth": "1990-01-01",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            "credit_report": {"status": "valid"},
            "application_form": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert any("identity" in m.lower() for m in missing)

    def test_name_mismatch(self):
        """Name mismatch across documents should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "full_name": "Jane Smith",  # Completely different name
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
                "applicant_name": "John Doe",
                "date_of_birth": "1990-01-01",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            "credit_report": {"status": "valid"},
            "application_form": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert any("name" in m.lower() for m in missing)

    def test_dob_mismatch(self):
        """Date of birth mismatch across documents should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John Doe",
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "full_name": "John Doe",
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
                "applicant_name": "John Doe",
                "date_of_birth": "1985-05-15",  # Different DOB
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            "credit_report": {"status": "valid"},
            "application_form": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert any("date of birth" in m.lower() or "dob" in m.lower() for m in missing)

    def test_name_with_minor_differences(self):
        """Names with minor differences (extra spacing, missing middle name) should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "full_name_en": "John  Michael  Doe",  # Extra spacing
                "date_of_birth": "1990-01-01",
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "full_name": "John Doe",  # Missing middle name
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
                "applicant_name": "John Michael Doe",
                "date_of_birth": "1990-01-01",
            },
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
            "credit_report": {"status": "valid"},
            "application_form": {"status": "valid"},
        }
        required_documents = ["emirates_id", "credit_report", "application_form"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        # "john michael doe" vs "john doe" = 0.67, vs "john michael doe" = 1.0
        # "john doe" vs "john michael doe" = 0.67 — all >= 0.6 threshold
        assert is_complete
        assert len(missing) == 0

    def test_empty_extracted_data(self):
        """Empty extracted data should fail."""
        extracted_data = {}
        validation_results = {}
        required_documents = ["emirates_id", "credit_report"]

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert not is_complete
        assert len(missing) > 0

    def test_no_required_documents(self):
        """No required documents should pass."""
        extracted_data = {
            "emirates_id": {"identity_number": "784-2000-1234567-2"},
        }
        validation_results = {
            "emirates_id": {"status": "valid"},
        }
        required_documents = []

        is_complete, missing = validate_completeness(
            validation_results, extracted_data, required_documents
        )
        assert is_complete
        assert len(missing) == 0
