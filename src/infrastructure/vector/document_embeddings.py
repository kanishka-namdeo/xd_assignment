"""Document embedding store - Qdrant vector operations."""

from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from src.infrastructure.vector.client import COLLECTION_NAME, ensure_collection


class DocumentEmbeddingStore:
    """Store and search document embeddings in Qdrant."""

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def initialize(self) -> None:
        """Ensure the collection exists."""
        await ensure_collection(self.client)

    async def upsert(
        self,
        point_id: str,
        vector: list[float],
        applicant_id: str,
        document_type: str,
        document_id: str | None = None,
        **extra_payload,
    ) -> None:
        """Upsert a document embedding with payload for filtering."""
        payload: dict = {
            "applicant_id": applicant_id,
            "document_type": document_type,
            **extra_payload,
        }
        if document_id is not None:
            payload["document_id"] = document_id

        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    async def search_by_applicant(
        self,
        query_vector: list[float],
        applicant_id: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """Search embeddings filtered by applicant_id."""
        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="applicant_id",
                        match=qdrant_models.MatchValue(value=applicant_id),
                    ),
                ]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]

    async def search_by_document_type(
        self,
        query_vector: list[float],
        document_type: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """Search embeddings filtered by document_type."""
        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="document_type",
                        match=qdrant_models.MatchValue(value=document_type),
                    ),
                ]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]

    async def search_by_applicant_and_type(
        self,
        query_vector: list[float],
        applicant_id: str,
        document_type: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """Search embeddings filtered by both applicant_id and document_type."""
        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="applicant_id",
                        match=qdrant_models.MatchValue(value=applicant_id),
                    ),
                    qdrant_models.FieldCondition(
                        key="document_type",
                        match=qdrant_models.MatchValue(value=document_type),
                    ),
                ]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]

    async def delete_by_applicant(self, applicant_id: str) -> None:
        """Delete all embeddings for an applicant."""
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="applicant_id",
                            match=qdrant_models.MatchValue(value=applicant_id),
                        ),
                    ]
                )
            ),
        )

    async def delete_by_document(self, document_id: str) -> None:
        """Delete an embedding for a specific document."""
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=document_id),
                        ),
                    ]
                )
            ),
        )
