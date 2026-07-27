"""Test checkpointer factory."""
import pytest
from unittest.mock import AsyncMock, patch
import src.agents.checkpointer as checkpointer_module
from src.agents.checkpointer import get_checkpointer


@pytest.fixture(autouse=True)
def reset_checkpointer_singleton():
    """Reset the singleton before each test."""
    checkpointer_module._checkpointer = None
    yield
    checkpointer_module._checkpointer = None


@pytest.mark.asyncio
async def test_get_checkpointer_returns_singleton():
    """Test that get_checkpointer returns the same instance."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        checkpointer1 = await get_checkpointer()
        checkpointer2 = await get_checkpointer()

        assert checkpointer1 is checkpointer2
        # Should only connect once
        assert mock_connect.call_count == 1
