"""Langfuse v4 integration for LLM observability and tracing."""

from __future__ import annotations

from typing import Any

import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class LangfuseClient:
    """Langfuse v4 client for trace collection and LangChain callback integration."""

    def __init__(self) -> None:
        self._client: Any = None
        self._enabled = False

        if not settings.LANGFUSE_ENABLED:
            logger.info("langfuse.disabled")
            return

        public_key = settings.LANGFUSE_PUBLIC_KEY.get_secret_value()
        secret_key = settings.LANGFUSE_SECRET_KEY.get_secret_value()

        if not public_key or not secret_key:
            logger.warning("langfuse.missing_keys", host=settings.LANGFUSE_HOST)
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=settings.LANGFUSE_HOST,
            )
            self._enabled = True
            logger.info("langfuse.initialized", host=settings.LANGFUSE_HOST)
        except Exception:
            logger.exception("langfuse.init_failed")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_callback_handler(self) -> Any:
        """Return a LangfuseCallbackHandler for LangChain/LangGraph integration.

        Returns None if Langfuse is not enabled or unavailable.
        Trace attributes should be set via propagate_attributes() context manager.
        """
        if not self._enabled or self._client is None:
            return None

        try:
            from langfuse.langchain import CallbackHandler

            handler = CallbackHandler()
            return handler
        except Exception:
            logger.exception("langfuse.callback_handler_failed")
            return None

    def trace(
        self,
        name: str,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        input: Any = None,
    ) -> Any:
        """Create a Langfuse trace. Returns None if disabled."""
        if not self._enabled or self._client is None:
            return None

        try:
            return self._client.trace(
                name=name,
                session_id=session_id,
                user_id=user_id,
                tags=tags or [],
                metadata=metadata or {},
                input=input,
            )
        except Exception:
            logger.exception("langfuse.trace_failed")
            return None

    def flush(self) -> None:
        """Flush pending traces to Langfuse server."""
        if not self._enabled or self._client is None:
            return

        try:
            self._client.flush()
            logger.debug("langfuse.flushed")
        except Exception:
            logger.exception("langfuse.flush_failed")

    def shutdown(self) -> None:
        """Flush and shut down the Langfuse client."""
        self.flush()
        self._client = None
        self._enabled = False
