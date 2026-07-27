"""Shared fixtures for evaluation tests."""

import json
from pathlib import Path

import pytest
import structlog

logger = structlog.get_logger(__name__)

EVALS_DATA_DIR = Path(__file__).parent.parent / "data" / "test_applicants"
PROFILES_FILE = EVALS_DATA_DIR / "profiles.json"


@pytest.fixture(scope="session")
def golden_profiles() -> dict[str, dict]:
    """Load all golden profiles from profiles.json."""
    if not PROFILES_FILE.exists():
        pytest.skip(f"Golden profiles not found at {PROFILES_FILE}")
    with open(PROFILES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    profiles = data.get("profiles", [])
    profile_map = {p["profile_name"]: p for p in profiles}

    logger.info(
        "golden_profiles_loaded",
        profile_count=len(profile_map),
        profiles=list(profile_map.keys()),
    )
    return profile_map


@pytest.fixture
def approved_profile(golden_profiles: dict[str, dict]) -> dict:
    """Get the profile expected to result in 'approved'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "approved":
            return profile
    pytest.skip("No approved profile found")


@pytest.fixture
def manual_review_profile(golden_profiles: dict[str, dict]) -> dict:
    """Get the profile expected to result in 'manual_review'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "manual_review":
            return profile
    pytest.skip("No manual_review profile found")


@pytest.fixture
def soft_decline_profile(golden_profiles: dict[str, dict]) -> dict:
    """Get the profile expected to result in 'soft_decline'."""
    for name, profile in golden_profiles.items():
        if profile.get("expected_decision") == "soft_decline":
            return profile
    pytest.skip("No soft_decline profile found")
