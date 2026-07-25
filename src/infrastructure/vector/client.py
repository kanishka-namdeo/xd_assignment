"""Qdrant async client setup - singleton pattern."""

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams

from src.config import Settings

_client: AsyncQdrantClient | None = None

COLLECTION_NAME = "document_embeddings"
EMBEDDING_DIM = 384  # Matches nomic-embed-text via FastEmbed


def get_client(settings: Settings) -> AsyncQdrantClient:
    """Return the singleton Qdrant async client, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
            grpc_port=settings.QDRANT_GRPC_PORT,
        )
    return _client


async def close_client() -> None:
    """Close the Qdrant client connection."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ensure_collection(client: AsyncQdrantClient) -> None:
    """Create the document_embeddings collection if it doesn't exist."""
    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]
    if COLLECTION_NAME not in collection_names:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
