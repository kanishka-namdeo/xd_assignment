"""Tests for state size estimation and validation."""

import pytest
from unittest.mock import patch
from src.utils.state_size import estimate_state_size, check_state_size


class TestEstimateStateSize:
    """Test state size estimation."""

    def test_empty_state(self):
        """Empty state has minimal size."""
        state = {}
        size = estimate_state_size(state)
        assert size > 0
        assert size < 1024  # Less than 1KB

    def test_small_state(self):
        """Small state is under 50KB threshold."""
        state = {
            "current_phase": "intake",
            "applicant_id": "test-123",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        size = estimate_state_size(state)
        assert size > 0
        assert size < 50 * 1024  # Less than 50KB

    def test_large_state(self):
        """Large state exceeds 50KB threshold."""
        # Create a state with large extracted data
        state = {
            "extracted_data": {
                f"doc_{i}": {"content": "x" * 10000, "metadata": {"key": "value"}}
                for i in range(10)
            },
            "messages": [{"content": "y" * 5000} for _ in range(10)],
        }
        size = estimate_state_size(state)
        assert size > 50 * 1024  # Exceeds 50KB

    def test_state_with_non_serializable_objects(self):
        """State with non-serializable objects falls back to sys.getsizeof."""
        class NonSerializable:
            pass
        
        state = {
            "custom_object": NonSerializable(),
            "normal_field": "test",
        }
        # Should not raise, should fall back to sys.getsizeof
        size = estimate_state_size(state)
        assert size > 0


class TestCheckStateSize:
    """Test state size checking and logging."""

    def test_small_state_no_warning(self):
        """Small state logs debug, not warning."""
        state = {"current_phase": "intake", "applicant_id": "test-123"}
        
        with patch("src.utils.state_size.logger") as mock_logger:
            size = check_state_size(state, node_name="intake_node")
            
            # Should log debug, not warning
            mock_logger.debug.assert_called_once()
            mock_logger.warning.assert_not_called()
            
            # Should return size in bytes
            assert size > 0

    def test_large_state_logs_warning(self):
        """Large state logs warning."""
        # Create a state that exceeds 50KB
        state = {
            "extracted_data": {
                f"doc_{i}": {"content": "x" * 10000}
                for i in range(10)
            }
        }
        
        with patch("src.utils.state_size.logger") as mock_logger:
            size = check_state_size(state, node_name="processing_node")
            
            # Should log warning
            mock_logger.warning.assert_called_once()
            mock_logger.debug.assert_not_called()
            
            # Should return size in bytes
            assert size > 50 * 1024

    def test_check_with_application_id(self):
        """Check includes application_id in logs."""
        state = {"current_phase": "intake"}
        
        with patch("src.utils.state_size.logger") as mock_logger:
            check_state_size(
                state,
                node_name="intake_node",
                application_id="app-123"
            )
            
            # Verify application_id was included in log call
            call_args = mock_logger.debug.call_args
            assert "application_id" in call_args.kwargs
            assert call_args.kwargs["application_id"] == "app-123"

    def test_check_without_optional_params(self):
        """Check works without optional parameters."""
        state = {"current_phase": "intake"}
        
        # Should not raise
        size = check_state_size(state)
        assert size > 0
