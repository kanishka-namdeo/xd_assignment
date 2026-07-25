"""Document lineage graph repository - Neo4j operations for provenance chains."""

from uuid import UUID
from datetime import datetime

from neo4j import AsyncDriver, AsyncTransaction
from neo4j._async.work.result import AsyncResult

from src.infrastructure.graph.models import DocumentNode, HasDocumentRel, SupersedesRel


class DocumentLineageRepository:
    """Manage document provenance and lineage in Neo4j."""

    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    async def link_document_to_applicant(
        self, applicant_id: UUID, document: DocumentNode, rel: HasDocumentRel | None = None
    ) -> None:
        """Link a :Document node to its :Applicant via :HAS_DOCUMENT."""
        async with self.driver.session() as session:
            await session.execute_write(
                self._link_document_tx, applicant_id, document, rel
            )

    @staticmethod
    async def _link_document_tx(
        tx: AsyncTransaction,
        applicant_id: UUID,
        document: DocumentNode,
        rel: HasDocumentRel | None,
    ) -> None:
        await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})
            MERGE (d:Document {id: $doc_id})
            SET d += $doc_props
            MERGE (a)-[r:HAS_DOCUMENT]->(d)
            SET r += $rel_props
            """,
            applicant_id=str(applicant_id),
            doc_id=str(document.id),
            doc_props=document.model_dump(exclude={"id"}),
            rel_props=rel.model_dump() if rel else {},
        )

    async def supersede_document(
        self, new_doc_id: UUID, old_doc_id: UUID, rel: SupersedesRel
    ) -> None:
        """Create a :SUPERSEDES relationship from a new document to an old one."""
        async with self.driver.session() as session:
            await session.execute_write(
                self._supersede_tx, new_doc_id, old_doc_id, rel
            )

    @staticmethod
    async def _supersede_tx(
        tx: AsyncTransaction,
        new_doc_id: UUID,
        old_doc_id: UUID,
        rel: SupersedesRel,
    ) -> None:
        await tx.run(
            """
            MATCH (old:Document {id: $old_doc_id})
            MATCH (new:Document {id: $new_doc_id})
            MERGE (new)-[r:SUPERSEDES]->(old)
            SET r += $rel_props
            """,
            old_doc_id=str(old_doc_id),
            new_doc_id=str(new_doc_id),
            rel_props=rel.model_dump(),
        )

    async def get_lineage(self, document_id: UUID) -> dict:
        """Return the full lineage (supersedes chain) for a document."""
        async with self.driver.session() as session:
            result = await session.execute_read(
                self._get_lineage_tx, document_id
            )
            return result

    @staticmethod
    async def _get_lineage_tx(
        tx: AsyncTransaction, document_id: UUID
    ) -> dict:
        cursor: AsyncResult = await tx.run(
            """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[r:SUPERSEDES*]->(ancestor:Document)
            OPTIONAL MATCH (descendant:Document)-[r2:SUPERSEDES*]->(d)
            RETURN d AS document,
                   collect(DISTINCT ancestor) AS ancestors,
                   collect(DISTINCT descendant) AS descendants
            """,
            document_id=str(document_id),
        )
        record = await cursor.single()
        if record is None:
            return {"document": None, "ancestors": [], "descendants": []}
        return {
            "document": dict(record["document"]),
            "ancestors": [dict(a) for a in record["ancestors"]],
            "descendants": [dict(d) for d in record["descendants"]],
        }

    async def get_validation_history(self, applicant_id: UUID) -> list[dict]:
        """Return all documents and their validation history for an applicant."""
        async with self.driver.session() as session:
            result = await session.execute_read(
                self._get_validation_history_tx, applicant_id
            )
            return result

    @staticmethod
    async def _get_validation_history_tx(
        tx: AsyncTransaction, applicant_id: UUID
    ) -> list[dict]:
        cursor: AsyncResult = await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})-[:HAS_DOCUMENT]->(d:Document)
            RETURN d AS document
            ORDER BY d.uploaded_at DESC
            """,
            applicant_id=str(applicant_id),
        )
        return [dict(record) async for record in cursor]
