"""Unit tests for eligibility rules gate."""

import pytest
from datetime import date, timedelta

from src.agents.gates.eligibility_rules import check_hard_eligibility_rules


class TestEmiratesIDEligibility:
    """Test Emirates ID eligibility checks."""

    def test_valid_emirates_id_passes(self):
        """Valid Emirates ID should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_expired_emirates_id_fails(self):
        """Expired Emirates ID should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "expired" in failure.lower()

    def test_invalid_checksum_fails(self):
        """Invalid Emirates ID checksum should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-0",  # Invalid check digit
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-0",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "checksum" in failure.lower() or "format" in failure.lower()

    def test_missing_emirates_id_fails(self):
        """Missing Emirates ID should fail."""
        extracted_data = {
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "emirates id" in failure.lower()


class TestCreditScoreEligibility:
    """Test credit score eligibility checks."""

    def test_valid_credit_score_passes(self):
        """Valid credit score should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "credit_score": 750,
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_low_credit_score_fails(self):
        """Credit score below 300 should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "credit_score": 250,
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "range" in failure.lower()

    def test_high_credit_score_fails(self):
        """Credit score above 900 should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "credit_score": 950,
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "range" in failure.lower()

    def test_missing_credit_report_passes(self):
        """Missing credit report should pass (not required)."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None


class TestIdentityConsistencyEligibility:
    """Test identity consistency eligibility checks."""

    def test_consistent_identities_pass(self):
        """Consistent identity numbers should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "credit_report": {
                "identity_number": "784-2000-1234567-2",
                "credit_score": 750,
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_inconsistent_identities_fail(self):
        """Inconsistent identity numbers should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "credit_report": {
                "identity_number": "784-2000-9999999-0",  # Different
                "credit_score": 750,
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "identity" in failure.lower() or "mismatch" in failure.lower()


class TestBankStatementEligibility:
    """Test bank statement eligibility checks."""

    def test_reconciled_bank_statement_passes(self):
        """Reconciled bank statement should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "bank_statement": {
                "opening_balance": "1000.00",
                "closing_balance": "1500.00",
                "total_debits": "500.00",
                "total_credits": "1000.00",
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "bank_statement": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_unreconciled_bank_statement_fails(self):
        """Unreconciled bank statement should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "bank_statement": {
                "opening_balance": "1000.00",
                "closing_balance": "1600.00",  # Wrong: should be 1500.00
                "total_debits": "500.00",
                "total_credits": "1000.00",
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "bank_statement": {"confidence": 0.90},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "reconciliation" in failure.lower()


class TestValidationConfidenceEligibility:
    """Test validation confidence eligibility checks."""

    def test_high_confidence_passes(self):
        """High validation confidence should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.85},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_low_confidence_fails(self):
        """Low validation confidence should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.65},  # Below 0.70
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "confidence" in failure.lower()


class TestRequiredDocumentsEligibility:
    """Test required documents eligibility checks."""

    def test_required_documents_present_passes(self):
        """Required documents present should pass."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            "application_form": {
                "identity_number": "784-2000-1234567-2",
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert passes
        assert failure is None

    def test_missing_required_document_fails(self):
        """Missing required document should fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            },
            # Missing application_form
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        assert "required" in failure.lower() or "not present" in failure.lower()


class TestMultipleFailures:
    """Test scenarios with multiple failures."""

    def test_first_failure_returned(self):
        """First failure should be returned when multiple checks fail."""
        extracted_data = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-0",  # Invalid checksum
                "expiry_date": (date.today() - timedelta(days=1)).isoformat(),  # Expired
            },
            "application_form": {
                "identity_number": "784-2000-9999999-0",  # Different identity
            },
        }
        validation_results = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        passes, failure = check_hard_eligibility_rules(extracted_data, validation_results)
        assert not passes
        # Should return the first failure encountered
        assert failure is not None
