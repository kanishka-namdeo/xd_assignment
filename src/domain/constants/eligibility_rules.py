"""Eligibility thresholds and support category requirements."""

# ---------------------------------------------------------------------------
# Support category score adjustments
# ---------------------------------------------------------------------------

CATEGORY_ADJUSTMENTS: dict[str, float] = {
    "divorced": 0.10,
    "abandoned": 0.15,
    "unknown_parentage": 0.12,
    "health_disability": 0.08,
}

# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------

APPROVAL_THRESHOLD = 0.70
MANUAL_REVIEW_THRESHOLD = 0.40
SOFT_DECLINE_THRESHOLD = 0.40

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------

EMPLOYMENT_STABILITY_MONTHS = 24  # Minimum for "stable" employment bonus
EMPLOYMENT_ADEQUATE_MONTHS = 12  # Minimum for "adequate" employment

CREDIT_SCORE_EXCELLENT = 750
CREDIT_SCORE_GOOD = 700
CREDIT_SCORE_FAIR = 650
CREDIT_SCORE_POOR = 500

DEBT_TO_INCOME_LOW = 0.30
DEBT_TO_INCOME_MODERATE = 0.50
DEBT_TO_INCOME_HIGH = 0.80

HOUSING_COST_AFFORDABLE = 0.25
HOUSING_COST_HIGH = 0.40

# ---------------------------------------------------------------------------
# Score components
# ---------------------------------------------------------------------------

BASE_SCORE = 0.4  # Starting score before adjustments

VALID_ID_BONUS = 0.10
EXCELLENT_CREDIT_BONUS = 0.20
GOOD_CREDIT_BONUS = 0.15
FAIR_CREDIT_BONUS = 0.08
VERY_POOR_CREDIT_PENALTY = -0.10

CLEAN_PAYMENT_HISTORY_BONUS = 0.05
MINOR_PAYMENT_ISSUES_PENALTY = -0.05
EXCESSIVE_LATE_PAYMENTS_PENALTY = -0.15
DEFAULTED_ACCOUNTS_PENALTY = -0.20

HEALTHY_SAVINGS_BONUS = 0.10
ADEQUATE_SAVINGS_BONUS = 0.05

STABLE_EMPLOYMENT_BONUS = 0.10
ADEQUATE_EMPLOYMENT_BONUS = 0.05
SHORT_EMPLOYMENT_PENALTY = -0.05

STRONG_NET_WORTH_BONUS = 0.08
POSITIVE_NET_WORTH_BONUS = 0.04
NEGATIVE_NET_WORTH_PENALTY = -0.10

LARGE_FAMILY_BONUS = 0.05

AFFORDABLE_HOUSING_BONUS = 0.05
HIGH_HOUSING_COST_PENALTY = -0.05
