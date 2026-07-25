"""Unit tests for document integrity gate."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.agents.gates.document_integrity import validate_document_integrity


class TestEmiratesIDValidation:
    """Test Emirates ID document integrity validation."""

    def test_valid_emirates_id(self):
        """Valid Emirates ID should pass all checks."""
        data = {
            "identity_number": "784-2000-1234567-2",
            "full_name_en": "John Doe",
            "nationality": "UAE",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "is_mrz_verified": True,
        }
        is_valid, errors = validate_document_integrity(data, "emirates_id")
        assert is_valid
        assert len(errors) == 0

    def test_expired_emirates_id(self):
        """Expired Emirates ID should fail."""
        data = {
            "identity_number": "784-2000-1234567-2",
            "full_name_en": "John Doe",
            "nationality": "UAE",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "expiry_date": (date.today() - timedelta(days=1)).isoformat(),
            "is_mrz_verified": True,
        }
        is_valid, errors = validate_document_integrity(data, "emirates_id")
        assert not is_valid
        assert any("expired" in err.lower() for err in errors)

    def test_invalid_checksum(self):
        """Invalid Luhn checksum should fail."""
        data = {
            "identity_number": "784-2000-1234567-0",  # Invalid check digit
            "full_name_en": "John Doe",
            "nationality": "UAE",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "is_mrz_verified": True,
        }
        is_valid, errors = validate_document_integrity(data, "emirates_id")
        assert not is_valid
        assert any("checksum" in err.lower() or "format" in err.lower() for err in errors)

    def test_mrZ_not_verified(self):
        """MRZ not verified should fail."""
        data = {
            "identity_number": "784-2000-1234567-2",
            "full_name_en": "John Doe",
            "nationality": "UAE",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "is_mrz_verified": False,
        }
        is_valid, errors = validate_document_integrity(data, "emirates_id")
        assert not is_valid
        assert any("mrz" in err.lower() for err in errors)

    def test_missing_required_field(self):
        """Missing required field should fail."""
        data = {
            "full_name_en": "John Doe",
            "nationality": "UAE",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "is_mrz_verified": True,
        }
        is_valid, errors = validate_document_integrity(data, "emirates_id")
        assert not is_valid
        assert any("identity_number" in err for err in errors)


class TestBankStatementValidation:
    """Test bank statement document integrity validation."""

    def test_valid_bank_statement(self):
        """Valid bank statement should pass all checks."""
        data = {
            "bank_name": "Emirates NBD",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "currency": "AED",
            "statement_period_start": "2024-01-01",
            "statement_period_end": "2024-01-31",
            "opening_balance": "1000.00",
            "closing_balance": "1500.00",
            "total_debits": "500.00",
            "total_credits": "1000.00",
            "transactions": [],
        }
        is_valid, errors = validate_document_integrity(data, "bank_statement")
        assert is_valid
        assert len(errors) == 0

    def test_balance_reconciliation_failure(self):
        """Balance reconciliation failure should fail."""
        data = {
            "bank_name": "Emirates NBD",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "currency": "AED",
            "statement_period_start": "2024-01-01",
            "statement_period_end": "2024-01-31",
            "opening_balance": "1000.00",
            "closing_balance": "1600.00",  # Wrong: should be 1500.00
            "total_debits": "500.00",
            "total_credits": "1000.00",
            "transactions": [],
        }
        is_valid, errors = validate_document_integrity(data, "bank_statement")
        assert not is_valid
        assert any("reconciliation" in err.lower() for err in errors)

    def test_invalid_statement_period(self):
        """Statement period where start >= end should fail."""
        data = {
            "bank_name": "Emirates NBD",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "currency": "AED",
            "statement_period_start": "2024-01-31",
            "statement_period_end": "2024-01-01",  # End before start
            "opening_balance": "1000.00",
            "closing_balance": "1500.00",
            "total_debits": "500.00",
            "total_credits": "1000.00",
            "transactions": [],
        }
        is_valid, errors = validate_document_integrity(data, "bank_statement")
        assert not is_valid
        assert any("period" in err.lower() for err in errors)

    def test_future_transaction_date(self):
        """Future transaction date should fail."""
        future_date = (date.today() + timedelta(days=30)).isoformat()
        data = {
            "bank_name": "Emirates NBD",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "currency": "AED",
            "statement_period_start": "2024-01-01",
            "statement_period_end": "2024-01-31",
            "opening_balance": "1000.00",
            "closing_balance": "1500.00",
            "total_debits": "500.00",
            "total_credits": "1000.00",
            "transactions": [
                {"transaction_date": future_date, "amount": "100.00"}
            ],
        }
        is_valid, errors = validate_document_integrity(data, "bank_statement")
        assert not is_valid
        assert any("future" in err.lower() for err in errors)

    def test_non_aed_currency(self):
        """Non-AED currency should fail."""
        data = {
            "bank_name": "Emirates NBD",
            "account_holder_name": "John Doe",
            "account_number": "1234567890",
            "currency": "USD",
            "statement_period_start": "2024-01-01",
            "statement_period_end": "2024-01-31",
            "opening_balance": "1000.00",
            "closing_balance": "1500.00",
            "total_debits": "500.00",
            "total_credits": "1000.00",
            "transactions": [],
        }
        is_valid, errors = validate_document_integrity(data, "bank_statement")
        assert not is_valid
        assert any("currency" in err.lower() for err in errors)


class TestCreditReportValidation:
    """Test credit report document integrity validation."""

    def test_valid_credit_report(self):
        """Valid credit report should pass all checks."""
        data = {
            "cb_subject_id": "SUBJ123",
            "identity_number": "784-2000-1234567-2",
            "full_name": "John Doe",
            "credit_score": 750,
            "risk_band": "Low",
            "total_active_accounts": 3,
            "total_closed_accounts": 2,
            "total_outstanding_balance": "5000.00",
            "active_facilities": [
                {"current_balance": "3000.00"},
                {"current_balance": "2000.00"},
            ],
            "payment_history": [],
        }
        is_valid, errors = validate_document_integrity(data, "credit_report")
        assert is_valid
        assert len(errors) == 0

    def test_credit_score_out_of_range(self):
        """Credit score outside 300-900 range should fail."""
        data = {
            "cb_subject_id": "SUBJ123",
            "identity_number": "784-2000-1234567-2",
            "full_name": "John Doe",
            "credit_score": 250,  # Below 300
            "risk_band": "Low",
            "total_active_accounts": 3,
            "total_closed_accounts": 2,
            "total_outstanding_balance": "5000.00",
            "active_facilities": [],
            "payment_history": [],
        }
        is_valid, errors = validate_document_integrity(data, "credit_report")
        assert not is_valid
        assert any("range" in err.lower() for err in errors)

    def test_outstanding_balance_mismatch(self):
        """Total outstanding != sum of facility balances should fail."""
        data = {
            "cb_subject_id": "SUBJ123",
            "identity_number": "784-2000-1234567-2",
            "full_name": "John Doe",
            "credit_score": 750,
            "risk_band": "Low",
            "total_active_accounts": 3,
            "total_closed_accounts": 2,
            "total_outstanding_balance": "6000.00",  # Wrong: should be 5000.00
            "active_facilities": [
                {"current_balance": "3000.00"},
                {"current_balance": "2000.00"},
            ],
            "payment_history": [],
        }
        is_valid, errors = validate_document_integrity(data, "credit_report")
        assert not is_valid
        assert any("outstanding" in err.lower() for err in errors)

    def test_future_payment_history_date(self):
        """Future payment history date should fail."""
        future_date = (date.today() + timedelta(days=30)).isoformat()
        data = {
            "cb_subject_id": "SUBJ123",
            "identity_number": "784-2000-1234567-2",
            "full_name": "John Doe",
            "credit_score": 750,
            "risk_band": "Low",
            "total_active_accounts": 3,
            "total_closed_accounts": 2,
            "total_outstanding_balance": "5000.00",
            "active_facilities": [],
            "payment_history": [
                {"date": future_date, "amount": "100.00"}
            ],
        }
        is_valid, errors = validate_document_integrity(data, "credit_report")
        assert not is_valid
        assert any("future" in err.lower() for err in errors)


class TestAssetsLiabilitiesValidation:
    """Test assets/liabilities document integrity validation."""

    def test_valid_assets_liabilities(self):
        """Valid assets/liabilities should pass all checks."""
        data = {
            "applicant_name": "John Doe",
            "statement_date": date.today().isoformat(),
            "cash_and_deposits": "5000.00",
            "savings_accounts": "10000.00",
            "investment_accounts": "15000.00",
            "retirement_accounts": "0.00",
            "real_estate_value": "0.00",
            "vehicle_value": "0.00",
            "other_assets": "0.00",
            "total_assets": "30000.00",
            "total_liabilities": "10000.00",
            "net_worth": "20000.00",
        }
        is_valid, errors = validate_document_integrity(data, "assets_liabilities")
        assert is_valid
        assert len(errors) == 0

    def test_net_worth_calculation_error(self):
        """Net worth != total_assets - total_liabilities should fail."""
        data = {
            "applicant_name": "John Doe",
            "statement_date": date.today().isoformat(),
            "cash_and_deposits": "5000.00",
            "savings_accounts": "10000.00",
            "investment_accounts": "15000.00",
            "retirement_accounts": "0.00",
            "real_estate_value": "0.00",
            "vehicle_value": "0.00",
            "other_assets": "0.00",
            "total_assets": "30000.00",
            "total_liabilities": "10000.00",
            "net_worth": "25000.00",  # Wrong: should be 20000.00
        }
        is_valid, errors = validate_document_integrity(data, "assets_liabilities")
        assert not is_valid
        assert any("net worth" in err.lower() for err in errors)

    def test_negative_values(self):
        """Negative asset or liability values should fail."""
        data = {
            "applicant_name": "John Doe",
            "statement_date": date.today().isoformat(),
            "cash_and_deposits": "5000.00",
            "savings_accounts": "10000.00",
            "investment_accounts": "15000.00",
            "retirement_accounts": "0.00",
            "real_estate_value": "0.00",
            "vehicle_value": "0.00",
            "other_assets": "0.00",
            "total_assets": "-30000.00",  # Negative
            "total_liabilities": "10000.00",
            "net_worth": "-40000.00",
        }
        is_valid, errors = validate_document_integrity(data, "assets_liabilities")
        assert not is_valid
        assert any("negative" in err.lower() for err in errors)

    def test_old_statement_date(self):
        """Statement date older than 6 months should fail."""
        old_date = (date.today() - timedelta(days=200)).isoformat()
        data = {
            "applicant_name": "John Doe",
            "statement_date": old_date,
            "cash_and_deposits": "5000.00",
            "savings_accounts": "10000.00",
            "investment_accounts": "15000.00",
            "retirement_accounts": "0.00",
            "real_estate_value": "0.00",
            "vehicle_value": "0.00",
            "other_assets": "0.00",
            "total_assets": "30000.00",
            "total_liabilities": "10000.00",
            "net_worth": "20000.00",
        }
        is_valid, errors = validate_document_integrity(data, "assets_liabilities")
        assert not is_valid
        assert any("6 months" in err or "older" in err.lower() for err in errors)

    def test_asset_categories_sum_mismatch(self):
        """Asset categories sum != total_assets should fail."""
        data = {
            "applicant_name": "John Doe",
            "statement_date": date.today().isoformat(),
            "cash_and_deposits": "5000.00",
            "savings_accounts": "10000.00",
            "investment_accounts": "15000.00",
            "retirement_accounts": "0.00",
            "real_estate_value": "0.00",
            "vehicle_value": "0.00",
            "other_assets": "0.00",
            "total_assets": "35000.00",  # Wrong: should be 30000.00
            "total_liabilities": "10000.00",
            "net_worth": "25000.00",
        }
        is_valid, errors = validate_document_integrity(data, "assets_liabilities")
        assert not is_valid
        assert any("categories" in err.lower() or "sum" in err.lower() for err in errors)


class TestResumeValidation:
    """Test resume document integrity validation."""

    def test_valid_resume(self):
        """Valid resume should pass all checks."""
        data = {
            "full_name": "John Doe",
            "work_experience": [
                {
                    "company": "Company A",
                    "start_date": "2020-01-01",
                    "end_date": "2022-12-31",
                    "is_current": False,
                },
                {
                    "company": "Company B",
                    "start_date": "2023-01-01",
                    "end_date": None,
                    "is_current": True,
                },
            ],
            "total_positions": 2,
        }
        is_valid, errors = validate_document_integrity(data, "resume")
        assert is_valid
        assert len(errors) == 0

    def test_invalid_date_range(self):
        """Start date >= end date should fail."""
        data = {
            "full_name": "John Doe",
            "work_experience": [
                {
                    "company": "Company A",
                    "start_date": "2022-12-31",
                    "end_date": "2020-01-01",  # End before start
                    "is_current": False,
                },
            ],
            "total_positions": 1,
        }
        is_valid, errors = validate_document_integrity(data, "resume")
        assert not is_valid
        assert any("date" in err.lower() for err in errors)

    def test_future_end_date(self):
        """Future end date should fail."""
        future_date = (date.today() + timedelta(days=30)).isoformat()
        data = {
            "full_name": "John Doe",
            "work_experience": [
                {
                    "company": "Company A",
                    "start_date": "2020-01-01",
                    "end_date": future_date,
                    "is_current": False,
                },
            ],
            "total_positions": 1,
        }
        is_valid, errors = validate_document_integrity(data, "resume")
        assert not is_valid
        assert any("future" in err.lower() for err in errors)

    def test_current_position_with_end_date(self):
        """Current position with non-null end date should fail."""
        data = {
            "full_name": "John Doe",
            "work_experience": [
                {
                    "company": "Company A",
                    "start_date": "2020-01-01",
                    "end_date": "2022-12-31",
                    "is_current": True,  # Current but has end date
                },
            ],
            "total_positions": 1,
        }
        is_valid, errors = validate_document_integrity(data, "resume")
        assert not is_valid
        assert any("current" in err.lower() and "end_date" in err.lower() for err in errors)


class TestApplicationFormValidation:
    """Test application form document integrity validation."""

    def test_valid_application_form(self):
        """Valid application form should pass all checks."""
        data = {
            "applicant_name": "John Doe",
            "identity_number": "784-2000-1234567-2",
            "date_of_birth": "1990-01-01",
            "nationality": "UAE",
            "contact_phone": "+971501234567",
            "employment_status": "Employed",
            "monthly_salary": "10000.00",
            "other_income": "2000.00",
            "total_monthly_income": "12000.00",
        }
        is_valid, errors = validate_document_integrity(data, "application_form")
        assert is_valid
        assert len(errors) == 0

    def test_income_calculation_error(self):
        """Total income != salary + other income should fail."""
        data = {
            "applicant_name": "John Doe",
            "identity_number": "784-2000-1234567-2",
            "date_of_birth": "1990-01-01",
            "nationality": "UAE",
            "contact_phone": "+971501234567",
            "employment_status": "Employed",
            "monthly_salary": "10000.00",
            "other_income": "2000.00",
            "total_monthly_income": "15000.00",  # Wrong: should be 12000.00
        }
        is_valid, errors = validate_document_integrity(data, "application_form")
        assert not is_valid
        assert any("income" in err.lower() for err in errors)

    def test_missing_required_field(self):
        """Missing required field should fail."""
        data = {
            "applicant_name": "John Doe",
            "date_of_birth": "1990-01-01",
            "nationality": "UAE",
            "contact_phone": "+971501234567",
            "employment_status": "Employed",
            "monthly_salary": "10000.00",
            "other_income": "2000.00",
            "total_monthly_income": "12000.00",
        }
        is_valid, errors = validate_document_integrity(data, "application_form")
        assert not is_valid
        assert any("identity_number" in err for err in errors)


class TestUnknownDocumentType:
    """Test handling of unknown document types."""

    def test_unknown_document_type(self):
        """Unknown document type should log warning but not fail."""
        data = {"some_field": "some_value"}
        is_valid, errors = validate_document_integrity(data, "unknown_type")
        # Should pass since no required fields and no validator
        assert is_valid
        assert len(errors) == 0
