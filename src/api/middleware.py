"""Pure ASGI request logging middleware with correlation ID propagation."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        request = Request(scope)

        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-correlation-id":
                request_id = header_value.decode("utf-8")
                break

        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
        )

        start = time.perf_counter()
        logger.debug("request_started", method=request.method, path=request.url.path)

        try:
            async def send_wrapper(message: dict[str, object]) -> None:
                if message["type"] == "http.response.start":
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    status_code = message["status"]
                    headers = list(message.get("headers", []))
                    headers.append((b"x-correlation-id", request_id.encode("utf-8")))
                    message = {
                        **message,
                        "headers": headers,
                    }
                    logger.info(
                        "request_complete",
                        method=request.method,
                        path=request.url.path,
                        status_code=status_code,
                        duration_ms=round(elapsed_ms, 2),
                    )
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            clear_contextvars()
