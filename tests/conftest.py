"""Shared test fixtures."""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.infrastructure.db.session import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database session for unit tests."""
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def mock_neo4j() -> MagicMock:
    """Mock Neo4j driver."""
    driver = MagicMock()
    driver.session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    driver.session.return_value.__exit__ = MagicMock(return_value=None)
    return driver


@pytest.fixture
def mock_qdrant() -> MagicMock:
    """Mock Qdrant client."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM client."""
    client = AsyncMock()
    client.chat_completion = AsyncMock(return_value={
        "choices": [{"message": {"content": "Test response"}}],
        "usage": {"total_tokens": 100}
    })
    return client


@pytest.fixture
def data_dir():
    """Path to test data directory."""
    return Path(__file__).parent.parent / "data" / "test_applicants"


@pytest.fixture
def synthetic_profiles(data_dir):
    """Load all synthetic applicant profiles from data directory."""
    profiles = {}
    if data_dir.exists():
        for profile_dir in data_dir.iterdir():
            if profile_dir.is_dir():
                profile_file = profile_dir / "profile.json"
                if profile_file.exists():
                    with open(profile_file, encoding="utf-8") as f:
                        profiles[profile_dir.name] = json.load(f)
    return profiles


@pytest.fixture
def approved_profile(synthetic_profiles):
    """Get the profile expected to result in 'approved' decision."""
    for name, profile in synthetic_profiles.items():
        if profile.get("expected_decision") == "approved":
            return profile
    return next(iter(synthetic_profiles.values()), {})


@pytest.fixture
def manual_review_profile(synthetic_profiles):
    """Get the profile expected to result in 'manual_review' decision."""
    for name, profile in synthetic_profiles.items():
        if profile.get("expected_decision") == "manual_review":
            return profile
    return next(iter(synthetic_profiles.values()), {})


@pytest.fixture
def soft_decline_profile(synthetic_profiles):
    """Get the profile expected to result in 'soft_decline' decision."""
    for name, profile in synthetic_profiles.items():
        if profile.get("expected_decision") == "soft_decline":
            return profile
    return next(iter(synthetic_profiles.values()), {})


@pytest.fixture
def streamlake_settings():
    """Override settings to use StreamLake provider."""
    original_provider = settings.LLM_PROVIDER
    settings.LLM_PROVIDER = "streamlake"
    yield settings
    settings.LLM_PROVIDER = original_provider


@pytest.fixture
def mock_chat_openai():
    """Mock ChatOpenAI that returns controlled responses for ReAct agents."""
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"decision": "approved", "explanation": "Test decision"}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


@pytest.fixture
def sample_extracted_data():
    """Sample extracted data dict matching the schema used by agents."""
    return {
        "emirates_id": {
            "identity_number": "784-1990-1234567-6",
            "full_name_en": "Ahmed Mohammed Ali",
            "full_name_ar": "احمد محمد علي",
            "date_of_birth": "1990-05-15",
            "gender": "Male",
            "nationality": "UAE",
            "address": "Dubai, Al Barsha",
            "expiry_date": "2028-12-31",
        },
        "bank_statement": {
            "bank_name": "Emirates NBD",
            "account_holder": "Ahmed Mohammed Ali",
            "account_number": "1234567890",
            "currency": "AED",
            "opening_balance": 15000.0,
            "closing_balance": 18500.0,
            "total_credits": 25000.0,
            "total_debits": 21500.0,
            "monthly_salary": 12000.0,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
        },
        "credit_report": {
            "cb_subject_id": "SUBJ001",
            "identity_number": "784-1990-1234567-6",
            "full_name": "Ahmed Mohammed Ali",
            "credit_score": 720,
            "risk_band": "Good",
            "total_active_accounts": 3,
            "total_closed_accounts": 2,
            "total_outstanding_balance": "45000.00",
            "active_facilities": [
                {"current_balance": "20000.00", "monthly_payment": "800.00"},
                {"current_balance": "15000.00", "monthly_payment": "600.00"},
                {"current_balance": "10000.00", "monthly_payment": "400.00"},
            ],
            "payment_history": [],
        },
        "application_form": {
            "full_name": "Ahmed Mohammed Ali",
            "identity_number": "784-1990-1234567-6",
            "total_monthly_income": 12000.0,
            "employment_status": "employed",
            "support_category": "divorced",
            "family_size": 3,
            "has_dependents": True,
        },
    }


@pytest.fixture
def sample_state(sample_extracted_data):
    """Sample ApplicantState for testing agent nodes."""
    return {
        "messages": [],
        "current_phase": "processing",
        "applicant_id": "test-applicant-001",
        "application_id": "test-application-001",
        "uploaded_files": [],
        "eligibility_score": None,
        "decision": None,
        "decision_explanation": None,
        "uploaded_documents": [
            {"id": "doc-1", "type": "emirates_id", "path": "data/test/emirates_id.png"},
            {"id": "doc-2", "type": "bank_statement", "path": "data/test/bank_statement.pdf"},
            {"id": "doc-3", "type": "credit_report", "path": "data/test/credit_report.pdf"},
            {"id": "doc-4", "type": "application_form", "path": "data/test/application_form.png"},
        ],
        "discrepancies": [],
        "extracted_data": sample_extracted_data,
        "validation_errors": [],
        "identity_number": "784-1990-1234567-6",
        "support_category": "divorced",
        "extraction_confidence": {
            "emirates_id": 0.95,
            "bank_statement": 0.92,
            "credit_report": 0.90,
            "application_form": 0.88,
        },
        "validation_results": {},
        "eligibility_factors": None,
        "gate_status": "passed",
        "gate_errors": [],
        "retry_count": 0,
        "escalation_reason": None,
    }
