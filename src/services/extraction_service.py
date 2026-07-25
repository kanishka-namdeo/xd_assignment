"""Extraction service - orchestrate document data extraction pipeline."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.db.repositories.extraction_repo import (
    ApplicationFormRepository,
    AssetsLiabilitiesRepository,
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
    ResumeRepository,
)
from src.infrastructure.graph.document_lineage_repo import DocumentLineageRepository
from src.infrastructure.graph.models import DocumentNode, HasDocumentRel
from src.infrastructure.vector.document_embeddings import DocumentEmbeddingStore

logger = structlog.get_logger()


class ExtractionService:
    """Orchestrate document extraction, embedding, and lineage tracking."""

    def __init__(
        self,
        session: AsyncSession,
        neo4j_driver=None,
        qdrant_client=None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.emirates_id_repo = EmiratesIDRepository(session)
        self.bank_stmt_repo = BankStatementRepository(session)
        self.credit_report_repo = CreditReportRepository(session)
        self.resume_repo = ResumeRepository(session)
        self.assets_liabilities_repo = AssetsLiabilitiesRepository(session)
        self.application_form_repo = ApplicationFormRepository(session)
        self.neo4j_driver = neo4j_driver
        self.qdrant_client = qdrant_client

    async def extract_document(self, document_id: UUID) -> dict:
        """Extract data from a single document and store results."""
        document = await self.doc_repo.get_by_id(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        await self.doc_repo.update_status(document_id, processing_status="extracting")

        try:
            extraction_result = await self._run_extraction(document)

            await self._store_extraction_data(document.document_type, document_id, extraction_result)

            await self.doc_repo.update_status(
                document_id,
                processing_status="completed",
                extraction_status="success",
            )

            if document.overall_confidence is None:
                document.overall_confidence = extraction_result.get("confidence", 0.0)
                await self.doc_repo.update(document)

            await self._create_lineage(document)
            await self._create_embedding(document, extraction_result)

            logger.info(
                "document_extracted",
                document_id=str(document_id),
                document_type=document.document_type,
                confidence=extraction_result.get("confidence"),
            )
            return extraction_result

        except Exception as e:
            await self.doc_repo.update_status(
                document_id,
                processing_status="failed",
                extraction_status="failed",
            )
            document.error_log = str(e)
            await self.doc_repo.update(document)
            logger.error("document_extraction_failed", document_id=str(document_id), error=str(e))
            raise

    async def extract_all_documents(self, applicant_id: UUID) -> list[dict]:
        """Extract all uploaded documents for an applicant."""
        documents = await self.doc_repo.get_by_applicant(applicant_id)
        results = []
        for doc in documents:
            if doc.processing_status in ("uploaded", "failed"):
                try:
                    result = await self.extract_document(doc.id)
                    results.append({"document_id": str(doc.id), "status": "success", **result})
                except Exception as e:
                    results.append({"document_id": str(doc.id), "status": "failed", "error": str(e)})
        return results

    async def _run_extraction(self, document) -> dict:
        """Run the actual extraction pipeline for a document.

        This is a placeholder that returns structured data based on document type.
        Real extraction would use pymupdf4llm, paddleocr, camelot, etc.
        """
        from pathlib import Path

        file_path = Path(document.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {document.file_path}")

        return {
            "document_type": document.document_type,
            "file_path": str(file_path),
            "confidence": 0.85,
            "fields_extracted": 0,
            "raw_text_length": file_path.stat().st_size,
        }

    async def _store_extraction_data(
        self, document_type: str, document_id: UUID, data: dict
    ) -> None:
        """Store extracted data in the appropriate type-specific table."""
        repo_map = {
            "emirates_id": self.emirates_id_repo,
            "bank_statement": self.bank_stmt_repo,
            "credit_report": self.credit_report_repo,
            "resume": self.resume_repo,
            "assets_liabilities": self.assets_liabilities_repo,
            "application_form": self.application_form_repo,
        }
        repo = repo_map.get(document_type)
        if repo is None:
            logger.warning("no_extraction_repo", document_type=document_type)
            return

        existing = await repo.get_by_document_id(document_id)
        if existing is None:
            await repo.create(document_id=document_id, **data.get("extracted_fields", {}))
        else:
            await repo.upsert(document_id=document_id, **data.get("extracted_fields", {}))

    async def _create_lineage(self, document) -> None:
        """Record document lineage in Neo4j."""
        if self.neo4j_driver is None:
            return
        try:
            lineage_repo = DocumentLineageRepository(self.neo4j_driver)
            node = DocumentNode(
                id=document.id,
                applicant_id=document.applicant_id,
                document_type=document.document_type,
                file_hash=document.file_hash,
                uploaded_at=document.uploaded_at,
                processing_status=document.processing_status,
                extraction_status=document.extraction_status,
                validation_status=document.validation_status,
            )
            rel = HasDocumentRel(uploaded_at=document.uploaded_at)
            await lineage_repo.link_document_to_applicant(document.applicant_id, node, rel)
        except Exception as e:
            logger.warning("lineage_creation_failed", document_id=str(document.id), error=str(e))

    async def _create_embedding(self, document, extraction_result: dict) -> None:
        """Create document embedding in Qdrant."""
        if self.qdrant_client is None:
            return
        try:
            embedding_store = DocumentEmbeddingStore(self.qdrant_client)
            await embedding_store.initialize()

            text_content = f"{document.document_type} {document.file_hash}"
            from src.infrastructure.vector.client import EMBEDDING_DIM

            import hashlib

            hash_bytes = hashlib.sha256(text_content.encode()).digest()
            pseudo_vector = [
                (hash_bytes[i % len(hash_bytes)] / 255.0) * 2 - 1
                for i in range(EMBEDDING_DIM)
            ]
            norm = sum(v * v for v in pseudo_vector) ** 0.5
            vector = [v / norm for v in pseudo_vector]

            await embedding_store.upsert(
                point_id=str(document.id),
                vector=vector,
                applicant_id=str(document.applicant_id),
                document_type=document.document_type,
                document_id=str(document.id),
            )
        except Exception as e:
            logger.warning("embedding_creation_failed", document_id=str(document.id), error=str(e))
