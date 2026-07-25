"""Ollama-based embedding client with batch processing and normalization."""

from __future__ import annotations

import math

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from src.config import settings

logger = structlog.get_logger(__name__)


def _normalize(vector: list[float]) -> list[float]:
    """L2-normalize a vector for cosine similarity."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


class EmbeddingClient:
    """Async embedding client that always uses Ollama (local)."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.EMBEDDING_MODEL
        self._client = AsyncOpenAI(
            base_url=settings.OLLAMA_BASE_URL,
            api_key=settings.OLLAMA_API_KEY,
            timeout=30.0,
        )

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=1),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed a list of texts. Returns L2-normalized vectors."""
        if not texts:
            return []

        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]
        normalized = [_normalize(e) for e in embeddings]

        logger.debug(
            "embeddings.generated",
            model=self.model,
            count=len(texts),
            dimension=len(normalized[0]) if normalized else 0,
        )
        return normalized

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query with 'query: ' prefix for retrieval tasks."""
        prefixed = f"query: {text}"
        results = await self.embed([prefixed])
        return results[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents with 'passage: ' prefix for retrieval tasks."""
        prefixed = [f"passage: {t}" for t in texts]
        return await self.embed(prefixed)

    async def close(self) -> None:
        await self._client.close()
