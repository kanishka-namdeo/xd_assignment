"""Error classification utility for determining error handling strategy."""

from enum import Enum


class ErrorType(Enum):
    """Error categories for determining handling strategy."""
    TRANSIENT = "transient"  # Can retry
    BUSINESS_RULE = "business_rule"  # Should not retry
    LLM_ERROR = "llm_error"  # May retry with backoff
    PROGRAMMING = "programming"  # Should not retry, fail fast


def classify_error(error: Exception) -> ErrorType:
    """Classify an exception to determine handling strategy.

    Args:
        error: The exception to classify

    Returns:
        ErrorType indicating the category of error
    """
    error_class_name = error.__class__.__name__

    # TRANSIENT errors - can retry
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return ErrorType.TRANSIENT

    # LLM errors - may retry with backoff
    if error_class_name in ("RateLimitError", "ContextLengthExceededError"):
        return ErrorType.LLM_ERROR

    # BUSINESS_RULE errors - should not retry
    if isinstance(error, (ValueError, KeyError)):
        return ErrorType.BUSINESS_RULE

    # PROGRAMMING errors - should not retry, fail fast
    if isinstance(error, (AssertionError, TypeError, AttributeError)):
        return ErrorType.PROGRAMMING

    # Default to PROGRAMMING for unknown errors (fail fast)
    return ErrorType.PROGRAMMING
