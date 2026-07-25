"""OpenAI-compatible async LLM client with retry, streaming, and token tracking."""

from __future__ import annotations

import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import structlog
from openai import AsyncOpenAI, APIStatusError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from src.config import settings

logger = structlog.get_logger(__name__)

_RETRYABLE = (RateLimitError, APIStatusError)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    return False


@dataclass(slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def record(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion


@dataclass(slots=True)
class LLMClient:
    """Async OpenAI-compatible client supporting Ollama (local) and StreamLake (cloud)."""

    provider: str = field(default_factory=lambda: settings.LLM_PROVIDER)
    _client: AsyncOpenAI | None = field(default=None, init=False, repr=False)
    usage: TokenUsage = field(default_factory=TokenUsage, init=False)

    def __post_init__(self) -> None:
        self._client = self._build_client()

    def _build_client(self) -> AsyncOpenAI:
        if self.provider == "streamlake":
            api_key = settings.STREAMLAKE_API_KEY.get_secret_value()
            base_url = settings.STREAMLAKE_BASE_URL
        else:
            api_key = settings.OLLAMA_API_KEY
            base_url = settings.OLLAMA_BASE_URL

        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=float(settings.LLM_TIMEOUT),
        )

    @property
    def model(self) -> str:
        if self.provider == "streamlake":
            return settings.STREAMLAKE_MODEL
        return settings.OLLAMA_MODEL

    def get_model_name(self) -> str:
        return self.model

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60, jitter=1),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Non-streaming chat completion with retry and token tracking."""
        assert self._client is not None
        model = model or self.model
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS

        start = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.perf_counter() - start

        usage = response.usage
        if usage:
            self.usage.record(
                prompt=usage.prompt_tokens or 0,
                completion=usage.completion_tokens or 0,
            )

        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "model": response.model,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "latency_ms": round(elapsed * 1000, 1),
        }

        logger.info(
            "llm.completion",
            model=model,
            tokens=result["usage"]["total_tokens"],
            latency_ms=result["latency_ms"],
            finish_reason=choice.finish_reason,
        )
        return result

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Streaming chat completion. Yields content deltas."""
        assert self._client is not None
        model = model or self.model
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS

        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60, jitter=1),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def structured_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Chat completion with JSON mode for structured output.

        Sends response_format={\"type\": \"json_object\"} to request
        JSON-only output from the model. Falls back to parsing the raw
        text content if the provider does not support JSON mode.
        """
        assert self._client is not None
        model = model or self.model
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS

        start = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception:
            # Provider may not support response_format; fall back to regular completion
            logger.warning("json_mode_unsupported_fallback", model=model)
            return await self.chat_completion(messages, model=model, temperature=temperature, max_tokens=max_tokens)

        elapsed = time.perf_counter() - start

        usage = response.usage
        if usage:
            self.usage.record(
                prompt=usage.prompt_tokens or 0,
                completion=usage.completion_tokens or 0,
            )

        choice = response.choices[0]
        content = choice.message.content or ""

        result = {
            "content": content,
            "model": response.model,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "latency_ms": round(elapsed * 1000, 1),
        }

        logger.info(
            "llm.structured_completion",
            model=model,
            tokens=result["usage"]["total_tokens"],
            latency_ms=result["latency_ms"],
            finish_reason=choice.finish_reason,
        )
        return result

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
