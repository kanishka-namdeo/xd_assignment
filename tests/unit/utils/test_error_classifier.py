"""Test error classification utility."""
import pytest
from src.utils.error_classifier import classify_error, ErrorType


def test_classify_transient_errors():
    """Test that transient errors are classified correctly."""
    assert classify_error(ConnectionError("network down")) == ErrorType.TRANSIENT
    assert classify_error(TimeoutError("timeout")) == ErrorType.TRANSIENT
    assert classify_error(OSError("connection refused")) == ErrorType.TRANSIENT


def test_classify_business_rule_errors():
    """Test that business rule errors are classified correctly."""
    assert classify_error(ValueError("invalid input")) == ErrorType.BUSINESS_RULE
    assert classify_error(KeyError("missing key")) == ErrorType.BUSINESS_RULE


def test_classify_llm_errors():
    """Test that LLM errors are classified correctly."""
    # Mock LLM error classes
    class RateLimitError(Exception):
        pass

    class ContextLengthExceededError(Exception):
        pass

    assert classify_error(RateLimitError("rate limit")) == ErrorType.LLM_ERROR
    assert classify_error(ContextLengthExceededError("context too long")) == ErrorType.LLM_ERROR


def test_classify_programming_errors():
    """Test that programming errors are classified correctly."""
    assert classify_error(AssertionError("assertion failed")) == ErrorType.PROGRAMMING
    assert classify_error(TypeError("wrong type")) == ErrorType.PROGRAMMING
    assert classify_error(AttributeError("no attribute")) == ErrorType.PROGRAMMING


def test_classify_unknown_errors():
    """Test that unknown errors default to PROGRAMMING."""
    class CustomError(Exception):
        pass

    # Unknown errors should be classified as PROGRAMMING (fail fast)
    assert classify_error(CustomError("custom")) == ErrorType.PROGRAMMING
