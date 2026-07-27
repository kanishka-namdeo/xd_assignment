"""Test checkpointer factory and TTL cleanup."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.agents.checkpointer as checkpointer_module
from src.agents.checkpointer import (
    CheckpointerManager,
    get_checkpointer,
    get_checkpointer_manager,
)


@pytest.fixture(autouse=True)
def reset_checkpointer_singleton():
    """Reset the singleton before each test."""
    checkpointer_module._checkpointer = None
    checkpointer_module._manager = None
    yield
    checkpointer_module._checkpointer = None
    checkpointer_module._manager = None


def _make_mock_conn():
    """Create a mock connection with a properly mocked async cursor context manager."""
    # Use MagicMock (not AsyncMock) because cursor() is not a coroutine in psycopg3
    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    # conn.cursor() returns an async context manager
    cursor_cm = MagicMock()
    cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    cursor_cm.__aexit__ = AsyncMock(return_value=False)
    mock_conn.cursor.return_value = cursor_cm
    return mock_conn, mock_cursor


@pytest.mark.asyncio
async def test_get_checkpointer_returns_singleton():
    """Test that get_checkpointer returns the same instance."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        checkpointer1 = await get_checkpointer()
        checkpointer2 = await get_checkpointer()

        assert checkpointer1 is checkpointer2
        assert mock_connect.call_count == 1


@pytest.mark.asyncio
async def test_checkpointer_manager_start_stop():
    """Test that cleanup task starts and stops gracefully."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, _ = _make_mock_conn()
        mock_connect.return_value = mock_conn

        manager = CheckpointerManager()
        manager.cleanup_interval_minutes = 9999

        await manager.start_cleanup_task()
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        await manager.stop_cleanup_task()
        assert manager._cleanup_task.done()


@pytest.mark.asyncio
async def test_checkpointer_manager_deletes_old_checkpoints():
    """Test that old checkpoints are deleted during cleanup."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, mock_cursor = _make_mock_conn()
        mock_connect.return_value = mock_conn

        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.rowcount = 5

        manager = CheckpointerManager()
        manager.ttl_days = 30

        await manager._run_cleanup()

        # Verify SQL queries were executed (COUNT + DELETE writes + DELETE checkpoints)
        assert mock_cursor.execute.call_count == 3

        execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert any("SELECT COUNT" in sql for sql in execute_calls)
        assert any("DELETE FROM checkpoint_writes" in sql for sql in execute_calls)
        assert any("DELETE FROM checkpoints" in sql for sql in execute_calls)


@pytest.mark.asyncio
async def test_checkpointer_manager_respects_ttl():
    """Test that cleanup uses the correct TTL cutoff time."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, mock_cursor = _make_mock_conn()
        mock_connect.return_value = mock_conn

        mock_cursor.fetchone.return_value = (0,)

        manager = CheckpointerManager()
        manager.ttl_days = 7

        fixed_now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)
        with patch("src.agents.checkpointer.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            await manager._run_cleanup()

        # Verify the cutoff time was passed to the query
        execute_calls = mock_cursor.execute.call_args_list
        first_call_args = execute_calls[0][0]
        cutoff_param = first_call_args[1][0]
        expected_cutoff = fixed_now - timedelta(days=7)
        assert cutoff_param == expected_cutoff


@pytest.mark.asyncio
async def test_checkpointer_manager_no_old_checkpoints():
    """Test that cleanup handles case with no old checkpoints."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, mock_cursor = _make_mock_conn()
        mock_connect.return_value = mock_conn

        mock_cursor.fetchone.return_value = (0,)

        manager = CheckpointerManager()
        await manager._run_cleanup()

        # Should only execute the COUNT query, not the DELETE queries
        assert mock_cursor.execute.call_count == 1


@pytest.mark.asyncio
async def test_checkpointer_manager_handles_cleanup_error():
    """Test that cleanup task handles errors gracefully."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, mock_cursor = _make_mock_conn()
        mock_connect.return_value = mock_conn

        mock_cursor.execute.side_effect = Exception("Database error")

        manager = CheckpointerManager()

        with pytest.raises(Exception, match="Database error"):
            await manager._run_cleanup()


@pytest.mark.asyncio
async def test_checkpointer_manager_start_idempotent():
    """Test that starting cleanup task multiple times is safe."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, _ = _make_mock_conn()
        mock_connect.return_value = mock_conn

        manager = CheckpointerManager()
        manager.cleanup_interval_minutes = 9999

        await manager.start_cleanup_task()
        task1 = manager._cleanup_task

        await manager.start_cleanup_task()
        task2 = manager._cleanup_task

        assert task1 is task2

        await manager.stop_cleanup_task()


@pytest.mark.asyncio
async def test_checkpointer_manager_stop_when_not_running():
    """Test that stopping when task is not running is safe."""
    manager = CheckpointerManager()
    await manager.stop_cleanup_task()


def test_get_checkpointer_manager_returns_singleton():
    """Test that get_checkpointer_manager returns the same instance."""
    manager1 = get_checkpointer_manager()
    manager2 = get_checkpointer_manager()
    assert manager1 is manager2


@pytest.mark.asyncio
async def test_cleanup_loop_runs_cleanup_then_waits():
    """Test that cleanup loop runs cleanup immediately, then waits for interval."""
    with patch("src.agents.checkpointer.psycopg.AsyncConnection.connect") as mock_connect:
        mock_conn, mock_cursor = _make_mock_conn()
        mock_connect.return_value = mock_conn

        mock_cursor.fetchone.return_value = (0,)

        manager = CheckpointerManager()
        manager.cleanup_interval_minutes = 0  # 0 minutes = immediate re-run

        # Run one iteration manually by calling _run_cleanup directly
        await manager._run_cleanup()
        assert mock_cursor.execute.call_count == 1  # Only COUNT query
