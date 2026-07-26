"""Extraction persistence helpers - DB, Neo4j, Qdrant operations."""

import hashlib
from uuid import UUID

import structlog

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
from src.infrastructure.vector.client import EMBEDDING_DIM

logger = structlog.get_logger(__name__)


async def store_extraction_data(
    document_type: str,
    document_id: UUID,
    data: dict,
    emirates_id_repo: EmiratesIDRepository,
    bank_stmt_repo: BankStatementRepository,
    credit_report_repo: CreditReportRepository,
    resume_repo: ResumeRepository,
    assets_liabilities_repo: AssetsLiabilitiesRepository,
    application_form_repo: ApplicationFormRepository,
) -> None:
    """Store extracted data in the appropriate type-specific table."""
    repo_map = {
        "emirates_id": emirates_id_repo,
        "bank_statement": bank_stmt_repo,
        "credit_report": credit_report_repo,
        "resume": resume_repo,
        "assets_liabilities": assets_liabilities_repo,
        "application_form": application_form_repo,
    }
    repo = repo_map.get(document_type)
    if repo is None:
        logger.warning("no_extraction_repo", document_type=document_type)
        return

    extracted_fields = data.get("extracted_fields", {})
    extracted_fields["extraction_confidence"] = data.get("confidence", 0.0)

    existing = await repo.get_by_document_id(document_id)
    if existing is None:
        await repo.create(document_id=document_id, **extracted_fields)
    else:
        await repo.upsert(document_id=document_id, **extracted_fields)


async def create_lineage(document, neo4j_driver) -> None:
    """Record document lineage in Neo4j."""
    if neo4j_driver is None:
        return
    try:
        lineage_repo = DocumentLineageRepository(neo4j_driver)
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


async def create_embedding(document, extraction_result: dict, qdrant_client) -> None:
    """Create document embedding in Qdrant."""
    if qdrant_client is None:
        return
    try:
        embedding_store = DocumentEmbeddingStore(qdrant_client)
        await embedding_store.initialize()

        text_content = f"{document.document_type} {document.file_hash}"

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
