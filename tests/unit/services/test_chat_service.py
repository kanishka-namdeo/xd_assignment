"""Unit tests for ChatService exception handling."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.chat_service import ChatService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_application():
    app = MagicMock()
    app.id = "test-app-id"
    app.applicant_id = "test-applicant-id"
    app.current_phase = "document_collection"
    return app


@pytest.fixture
def chat_service(mock_session):
    with patch("src.services.chat_service.ApplicationRepository") as mock_repo_class:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock()
        mock_repo.get_state = AsyncMock()
        mock_repo.save_state = AsyncMock()
        mock_repo.update = AsyncMock()
        mock_repo_class.return_value = mock_repo
        service = ChatService(mock_session)
        service.application_repo = mock_repo
        yield service


@pytest.mark.asyncio
async def test_handle_chat_returns_graceful_error_when_orchestrator_crashes(chat_service, mock_application):
    """handle_chat returns a user-friendly error when orchestrator raises."""
    chat_service.application_repo.get_by_id.return_value = mock_application
    chat_service.application_repo.get_state.return_value = {
        "current_phase": "document_collection",
        "messages": [],
    }

    with patch("src.services.chat_service.run_orchestrator", side_effect=RuntimeError("Backend crash")):
        response = await chat_service.handle_chat(
            application_id="test-app-id",
            text="Process my documents",
            file_paths=[],
        )

    assert "error" in response.message.lower() or "try again" in response.message.lower()
    assert response.phase == "document_collection"
    assert response.decision is None


@pytest.mark.asyncio
async def test_handle_chat_returns_graceful_error_on_timeout(chat_service, mock_application):
    """handle_chat returns graceful response on timeout-like exceptions."""
    mock_application.current_phase = "processing"
    chat_service.application_repo.get_by_id.return_value = mock_application
    chat_service.application_repo.get_state.return_value = {
        "current_phase": "processing",
        "messages": [],
    }

    with patch("src.services.chat_service.run_orchestrator", side_effect=TimeoutError("LLM timeout")):
        response = await chat_service.handle_chat(
            application_id="test-app-id",
            text="Process my application",
            file_paths=[],
        )

    assert response.message
    assert response.phase == "processing"


@pytest.mark.asyncio
async def test_handle_chat_succeeds_when_orchestrator_returns(chat_service, mock_application):
    """handle_chat returns proper ChatResponse when orchestrator succeeds."""
    chat_service.application_repo.get_by_id.return_value = mock_application
    chat_service.application_repo.get_state.return_value = {
        "current_phase": "document_collection",
        "messages": [],
    }

    mock_result = {
        "current_phase": "review",
        "messages": [{"role": "assistant", "content": "Processing complete."}],
        "uploaded_documents": [],
        "decision": None,
        "extraction_results": [],
    }

    with patch("src.services.chat_service.run_orchestrator", return_value=mock_result):
        response = await chat_service.handle_chat(
            application_id="test-app-id",
            text="Process my documents",
            file_paths=[],
        )

    assert response.phase == "review"
    assert response.message == "Processing complete."
