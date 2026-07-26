"""Unit tests for eligibility agent nodes and tools."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.eligibility.nodes import (
    _build_applicant_features,
    eligibility_gate_node,
    eligibility_react_node,
)
from src.agents.eligibility.tools import (
    adjust_factor_weighting_tool,
    eligibility_explanation_tool,
    feature_importance_tool,
    ml_model_predict_tool,
)
from src.agents.gates.eligibility_rules import check_hard_eligibility_rules


class TestBuildApplicantFeatures:
    """Test feature extraction from extracted data."""

    def test_build_features_from_sample_data(self, sample_state):
        """Test that features are correctly extracted from sample state."""
        features = _build_applicant_features(sample_state)

        assert features["monthly_income"] == 12000.0
        assert features["family_size"] == 3
        assert features["support_category"] == "divorced"
        assert features["employment_status"] == "employed"
        assert features["has_dependents"] is True
        assert features["credit_score"] == 720
        assert "debt_to_income_ratio" in features
        assert "net_worth" in features
        assert "housing_cost_ratio" in features
        assert "employment_stability_months" in features

    def test_build_features_with_missing_data(self):
        """Test feature extraction with minimal data."""
        state = {
            "extracted_data": {
                "application_form": {
                    "total_monthly_income": 5000,
                    "family_size": 2,
                }
            }
        }
        features = _build_applicant_features(state)

        assert features["monthly_income"] == 5000.0
        assert features["family_size"] == 2
        assert features["has_dependents"] is True
        assert features["credit_score"] == 600  # default
        assert features["employment_stability_months"] == 0

    def test_build_features_calculates_ratios(self, sample_state):
        """Test that debt_to_income and housing_cost ratios are calculated."""
        features = _build_applicant_features(sample_state)

        # debt_to_income_ratio should be calculated
        assert isinstance(features["debt_to_income_ratio"], float)
        assert features["debt_to_income_ratio"] >= 0

        # housing_cost_ratio should be calculated
        assert isinstance(features["housing_cost_ratio"], float)
        assert features["housing_cost_ratio"] >= 0

    def test_build_features_with_zero_income(self):
        """Test feature extraction when income is zero."""
        state = {
            "extracted_data": {
                "application_form": {"total_monthly_income": 0},
                "credit_report": {"total_outstanding_balance": 10000},
            }
        }
        features = _build_applicant_features(state)

        assert features["debt_to_income_ratio"] == 0.0
        assert features["housing_cost_ratio"] == 0.0


class TestMlModelPredictTool:
    """Test ML model prediction tool."""

    def test_predict_with_synthetic_features(self):
        """Test prediction with synthetic features returns score 0-1."""
        features = {
            "monthly_income": 15000,
            "family_size": 3,
            "employment_stability_months": 24,
            "credit_score": 750,
            "debt_to_income_ratio": 0.3,
            "net_worth": 200000,
            "housing_cost_ratio": 0.25,
            "support_category": "divorced",
            "has_dependents": True,
            "employment_status": "employed",
        }

        result = ml_model_predict_tool.invoke({"applicant_features": features})

        assert "probability" in result
        assert "predicted_class" in result
        assert "method" in result
        assert 0.0 <= result["probability"] <= 1.0
        assert result["predicted_class"] in ["eligible", "not_eligible"]
        assert result["method"] == "rule_based"  # No ML model file

    def test_predict_fallback_without_model(self):
        """Test fallback to rule-based scoring when model file is missing."""
        features = {
            "monthly_income": 8000,
            "family_size": 2,
            "credit_score": 650,
            "debt_to_income_ratio": 0.4,
            "employment_stability_months": 12,
            "net_worth": 50000,
            "housing_cost_ratio": 0.3,
            "support_category": "abandoned",
            "has_dependents": True,
        }

        result = ml_model_predict_tool.invoke({"applicant_features": features})

        assert result["method"] == "rule_based"
        assert "factor_contributions" in result
        assert isinstance(result["factor_contributions"], dict)

    def test_predict_with_low_credit_score(self):
        """Test prediction with low credit score."""
        features = {
            "monthly_income": 5000,
            "credit_score": 450,
            "debt_to_income_ratio": 0.8,
            "employment_stability_months": 3,
            "net_worth": -10000,
        }

        result = ml_model_predict_tool.invoke({"applicant_features": features})

        assert result["probability"] < 0.60
        assert result["predicted_class"] == "not_eligible"

    def test_predict_with_high_credit_score(self):
        """Test prediction with high credit score."""
        features = {
            "monthly_income": 20000,
            "credit_score": 800,
            "debt_to_income_ratio": 0.2,
            "employment_stability_months": 48,
            "net_worth": 500000,
            "support_category": "divorced",
        }

        result = ml_model_predict_tool.invoke({"applicant_features": features})

        assert result["probability"] > 0.60
        assert result["predicted_class"] == "eligible"


class TestFeatureImportanceTool:
    """Test feature importance tool."""

    def test_returns_factor_contributions(self):
        """Test that tool returns factor contributions."""
        features = {
            "monthly_income": 12000,
            "credit_score": 720,
            "debt_to_income_ratio": 0.35,
            "employment_stability_months": 24,
            "net_worth": 150000,
            "housing_cost_ratio": 0.28,
            "support_category": "divorced",
            "family_size": 3,
        }

        result = feature_importance_tool.invoke(
            {"applicant_features": features, "n_top_features": 5}
        )

        assert "top_features" in result
        assert "method" in result
        assert isinstance(result["top_features"], list)
        assert result["method"] == "rule_based_factors"

    def test_fallback_without_model(self):
        """Test fallback to rule-based factors when model is unavailable."""
        features = {
            "monthly_income": 10000,
            "credit_score": 680,
            "debt_to_income_ratio": 0.5,
            "employment_stability_months": 18,
            "net_worth": 80000,
        }

        result = feature_importance_tool.invoke(
            {"applicant_features": features, "n_top_features": 3}
        )

        assert result["method"] == "rule_based_factors"
        assert len(result["top_features"]) <= 3

    def test_top_features_sorted_by_importance(self):
        """Test that top features are sorted by absolute importance."""
        features = {
            "monthly_income": 15000,
            "credit_score": 750,
            "debt_to_income_ratio": 0.2,
            "employment_stability_months": 36,
            "net_worth": 300000,
            "support_category": "abandoned",
        }

        result = feature_importance_tool.invoke(
            {"applicant_features": features, "n_top_features": 5}
        )

        if len(result["top_features"]) > 1:
            importances = [abs(f["importance"]) for f in result["top_features"]]
            assert importances == sorted(importances, reverse=True)


class TestAdjustFactorWeightingTool:
    """Test factor weighting adjustment tool."""

    def test_adjustment_for_support_category(self):
        """Test adjustment based on support category."""
        score = 0.55
        features = [
            {"feature": "credit_score", "importance": 0.15},
            {"feature": "employment_stability", "importance": 0.10},
        ]
        context = {
            "support_category": "divorced",
            "family_size": 2,
            "has_dependents": False,
            "employment_status": "employed",
        }

        result = adjust_factor_weighting_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
            }
        )

        assert "adjusted_score" in result
        assert "adjustment_amount" in result
        assert "reasoning" in result
        assert result["adjusted_score"] > score  # Divorced category adds adjustment
        assert "divorced" in result["reasoning"].lower()

    def test_adjustment_for_large_family(self):
        """Test adjustment for large family with dependents."""
        score = 0.60
        features = [{"feature": "credit_score", "importance": 0.12}]
        context = {
            "support_category": "abandoned",
            "family_size": 5,
            "has_dependents": True,
            "employment_status": "unemployed",
        }

        result = adjust_factor_weighting_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
            }
        )

        assert result["adjusted_score"] > score
        assert "family" in result["reasoning"].lower()

    def test_adjustment_for_employment_gap(self):
        """Test adjustment for unemployment with support category."""
        score = 0.50
        features = [{"feature": "employment_stability", "importance": -0.05}]
        context = {
            "support_category": "divorced",
            "family_size": 3,
            "has_dependents": True,
            "employment_status": "unemployed",
        }

        result = adjust_factor_weighting_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
            }
        )

        assert result["adjusted_score"] > score
        assert "transition" in result["reasoning"].lower() or "gap" in result["reasoning"].lower()

    def test_no_adjustment_for_general_category(self):
        """Test no adjustment for general support category."""
        score = 0.65
        features = [{"feature": "credit_score", "importance": 0.10}]
        context = {
            "support_category": "general",
            "family_size": 2,
            "has_dependents": False,
            "employment_status": "employed",
        }

        result = adjust_factor_weighting_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
            }
        )

        assert result["adjusted_score"] == score
        assert result["adjustment_amount"] == 0.0


class TestEligibilityExplanationTool:
    """Test eligibility explanation tool."""

    def test_generates_human_readable_explanation(self):
        """Test that tool generates human-readable explanation."""
        score = 0.72
        features = [
            {"feature": "credit_score", "importance": 0.15},
            {"feature": "employment_stability", "importance": 0.10},
            {"feature": "debt_ratio", "importance": -0.05},
        ]
        context = {
            "support_category": "divorced",
            "family_size": 3,
            "credit_score": 750,
        }
        validation_results = {"overall_confidence": 0.92}

        result = eligibility_explanation_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
                "validation_results": validation_results,
            }
        )

        assert "explanation" in result
        assert "key_factors" in result
        assert "recommendation" in result
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 50
        assert result["recommendation"] == "proceed_to_decision"

    def test_explanation_with_low_score(self):
        """Test explanation with low eligibility score."""
        score = 0.35
        features = [{"feature": "credit_score", "importance": -0.10}]
        context = {"support_category": "unknown", "credit_score": 450}
        validation_results = {}

        result = eligibility_explanation_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
                "validation_results": validation_results,
            }
        )

        assert "does not meet" in result["explanation"].lower() or "not meet" in result["explanation"].lower()
        assert result["recommendation"] == "likely_ineligible"

    def test_explanation_with_borderline_score(self):
        """Test explanation with borderline eligibility score."""
        score = 0.52
        features = [{"feature": "credit_score", "importance": 0.08}]
        context = {"support_category": "abandoned", "credit_score": 680}
        validation_results = {"overall_confidence": 0.85}

        result = eligibility_explanation_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
                "validation_results": validation_results,
            }
        )

        assert "borderline" in result["explanation"].lower() or "manual review" in result["explanation"].lower()
        assert result["recommendation"] == "manual_review"

    def test_key_factors_extracted(self):
        """Test that key factors are extracted from feature importance."""
        score = 0.68
        features = [
            {"feature": "credit_score", "importance": 0.20},
            {"feature": "employment_stability_months", "importance": 0.12},
            {"feature": "debt_to_income_ratio", "importance": -0.08},
        ]
        context = {"support_category": "divorced", "credit_score": 720}
        validation_results = {}

        result = eligibility_explanation_tool.invoke(
            {
                "eligibility_score": score,
                "feature_importance": features,
                "applicant_context": context,
                "validation_results": validation_results,
            }
        )

        assert len(result["key_factors"]) > 0
        assert "credit score" in result["key_factors"][0].lower()


class TestGate3Integration:
    """Test Gate 3 hard eligibility rules integration."""

    @pytest.mark.asyncio
    async def test_gate_passes_with_valid_data(self, sample_state):
        """Test gate passes with valid extracted data."""
        # Override extracted data with a valid Emirates ID (Luhn-valid)
        sample_state["extracted_data"] = {
            "emirates_id": {
                "identity_number": "784-2000-1234567-2",
                "expiry_date": "2028-12-31",
            },
            "bank_statement": {
                "opening_balance": 15000.0,
                "closing_balance": 18500.0,
                "total_credits": 25000.0,
                "total_debits": 21500.0,
            },
            "credit_report": {
                "identity_number": "784200012345672",
                "credit_score": 720,
            },
            "application_form": {
                "identity_number": "784200012345672",
                "total_monthly_income": 12000.0,
                "employment_status": "employed",
                "support_category": "divorced",
                "family_size": 3,
            },
        }
        sample_state["validation_results"] = {
            "emirates_id": {"confidence": 0.95},
            "bank_statement": {"confidence": 0.92},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.88},
        }

        result = await eligibility_gate_node(sample_state)

        assert result["gate_status"] == "passed"
        assert result["gate_errors"] == []

    @pytest.mark.asyncio
    async def test_gate_fails_with_invalid_emirates_id(self):
        """Test gate fails with invalid Emirates ID."""
        state = {
            "applicant_id": "test-001",
            "application_id": "app-001",
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-2000-1234567-0",  # Invalid checksum
                    "expiry_date": "2028-12-31",
                },
                "application_form": {"identity_number": "784-2000-1234567-0"},
            },
            "validation_results": {
                "emirates_id": {"confidence": 0.95},
                "application_form": {"confidence": 0.90},
            },
        }

        result = await eligibility_gate_node(state)

        assert result["gate_status"] == "failed"
        assert len(result["gate_errors"]) > 0
        assert "checksum" in result["gate_errors"][0].lower() or "format" in result["gate_errors"][0].lower()

    @pytest.mark.asyncio
    async def test_gate_fails_with_low_credit_score(self):
        """Test gate fails with credit score outside valid range."""
        from datetime import date, timedelta

        state = {
            "applicant_id": "test-002",
            "application_id": "app-002",
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-2000-1234567-2",
                    "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                },
                "credit_report": {
                    "identity_number": "784-2000-1234567-2",
                    "credit_score": 250,  # Below 300
                },
                "application_form": {"identity_number": "784-2000-1234567-2"},
            },
            "validation_results": {
                "emirates_id": {"confidence": 0.95},
                "credit_report": {"confidence": 0.90},
                "application_form": {"confidence": 0.90},
            },
        }

        result = await eligibility_gate_node(state)

        assert result["gate_status"] == "failed"
        assert "range" in result["gate_errors"][0].lower()

    @pytest.mark.asyncio
    async def test_gate_fails_with_identity_mismatch(self):
        """Test gate fails with inconsistent identity numbers."""
        from datetime import date, timedelta

        state = {
            "applicant_id": "test-003",
            "application_id": "app-003",
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-2000-1234567-2",
                    "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                },
                "credit_report": {
                    "identity_number": "784-2000-9999999-0",  # Different
                    "credit_score": 750,
                },
                "application_form": {"identity_number": "784-2000-1234567-2"},
            },
            "validation_results": {
                "emirates_id": {"confidence": 0.95},
                "credit_report": {"confidence": 0.90},
                "application_form": {"confidence": 0.90},
            },
        }

        result = await eligibility_gate_node(state)

        assert result["gate_status"] == "failed"
        assert "identity" in result["gate_errors"][0].lower() or "mismatch" in result["gate_errors"][0].lower()

    @pytest.mark.asyncio
    async def test_gate_fails_with_low_validation_confidence(self):
        """Test gate fails with low validation confidence."""
        from datetime import date, timedelta

        state = {
            "applicant_id": "test-004",
            "application_id": "app-004",
            "extracted_data": {
                "emirates_id": {
                    "identity_number": "784-2000-1234567-2",
                    "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                },
                "application_form": {"identity_number": "784-2000-1234567-2"},
            },
            "validation_results": {
                "emirates_id": {"confidence": 0.95},
                "application_form": {"confidence": 0.65},  # Below 0.70
            },
        }

        result = await eligibility_gate_node(state)

        assert result["gate_status"] == "failed"
        assert "confidence" in result["gate_errors"][0].lower()


class TestEligibilityGraph:
    """Test full eligibility graph execution."""

    @pytest.mark.asyncio
    async def test_graph_execution_with_mocked_tools(self, sample_state):
        """Test full graph execution with mocked tool internals."""
        # Add validation results
        sample_state["validation_results"] = {
            "emirates_id": {"confidence": 0.95},
            "bank_statement": {"confidence": 0.92},
            "credit_report": {"confidence": 0.90},
            "application_form": {"confidence": 0.88},
        }

        # Mock the internal ML model loader to force rule-based path
        with patch("src.agents.eligibility.tools._load_ml_model", return_value=None):
            result = await eligibility_react_node(sample_state)

            # Verify result structure
            assert "eligibility_score" in result
            assert "eligibility_factors" in result
            assert "messages" in result
            assert isinstance(result["eligibility_score"], float)
            assert 0.0 <= result["eligibility_score"] <= 1.0
            assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_graph_handles_tool_failure(self, sample_state):
        """Test graph handles tool failure gracefully via fallback path."""
        sample_state["validation_results"] = {
            "emirates_id": {"confidence": 0.95},
            "application_form": {"confidence": 0.90},
        }

        # Mock _build_applicant_features to raise on first call, succeed on second
        call_count = 0
        original_build = _build_applicant_features

        def flaky_build(state):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Simulated feature extraction error")
            return original_build(state)

        with patch(
            "src.agents.eligibility.nodes._build_applicant_features",
            side_effect=flaky_build,
        ):
            result = await eligibility_react_node(sample_state)

            # Should still return a result (fallback path uses rule-based scoring)
            assert "eligibility_score" in result
            assert "messages" in result
            assert isinstance(result["eligibility_score"], float)
