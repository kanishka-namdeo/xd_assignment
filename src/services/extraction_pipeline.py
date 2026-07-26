"""Core extraction pipeline - runs the appropriate parser based on file format."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.config import settings
from src.domain.parsers import parse_by_document_type
from src.domain.parsers.llm_extraction import parse_with_llm
from src.domain.parsers.text_extract import extract_text_from_pdf_result, extract_text_from_xlsx
from src.domain.scoring.confidence import (
    ConfidenceResult as ExtractionScore,
    compute_confidence as _domain_compute_confidence,
)
from src.infrastructure.db.repositories.extraction_repo import (
    ApplicationFormRepository,
    AssetsLiabilitiesRepository,
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
    ResumeRepository,
)
from src.infrastructure.db.session import get_session
from src.infrastructure.extraction_persistence import (
    create_embedding,
    create_lineage,
    store_extraction_data,
)
from src.infrastructure.graph.document_lineage_repo import DocumentLineageRepository
from src.infrastructure.graph.models import DocumentNode
from src.infrastructure.graph.driver import get_driver as get_neo4j_driver
from src.infrastructure.vector.client import get_client as get_qdrant_client
from src.infrastructure.vector.document_embeddings import DocumentEmbeddingStore
from src.services.validation_service import ValidationService

logger = structlog.get_logger(__name__)


async def run_extraction_pipeline(
    document,
    pdf_parser=None,
    ocr_engine=None,
    xlsx_extractor=None,
    resume_parser=None,
    llm_client=None,
    confidence_scorer=None,
) -> dict:
    """Run the extraction pipeline for a single document.

    Selects the appropriate parser based on file format, optionally enriches
    with LLM extraction, computes confidence, and returns a structured result.
    """
    file_path = Path(document.file_path)
    if not file_path.exists():
        logger.warning("file_not_found", document_id=str(document.id), file_path=str(file_path))
        raise FileNotFoundError(f"File not found: {document.file_path}")

    file_format = (document.file_format or "").lower()
    document_type = document.document_type

    raw_result = None
    parser_used = None
    raw_text = ""
    parsed_data: dict = {}

    try:
        if file_format == "pdf" and pdf_parser is not None:
            parser_used = "pdf_parser"
            raw_result = await pdf_parser.extract(file_path)
            raw_text = extract_text_from_pdf_result(raw_result)
            parsed_data = parse_by_document_type(document_type, raw_text, raw_result)
        elif file_format in ("png", "jpg", "jpeg") and ocr_engine is not None:
            parser_used = "ocr_engine"
            raw_result = await ocr_engine.extract(file_path)
            raw_text = raw_result.text
            parsed_data = parse_by_document_type(document_type, raw_text, raw_result)
        elif file_format == "xlsx" and xlsx_extractor is not None:
            parser_used = "xlsx_extractor"
            raw_result = await xlsx_extractor.extract(file_path)
            raw_text = extract_text_from_xlsx(raw_result)
            parsed_data = parse_by_document_type(document_type, raw_text, raw_result)
        elif file_format == "docx" and resume_parser is not None:
            parser_used = "resume_parser"
            raw_result = await resume_parser.parse(file_path)
            raw_text = str(raw_result.raw_extracted_data)
            parsed_data = parse_by_document_type(document_type, raw_text, raw_result)
        else:
            parser_used = "placeholder"
            parsed_data = parse_by_document_type(document_type, "", None)

        if llm_client is not None and raw_text:
            try:
                llm_fields = await parse_with_llm(llm_client, document_type, raw_text)
                if llm_fields:
                    for key, value in llm_fields.items():
                        if key not in ("raw_text", "parsed"):
                            parsed_data[key] = value
                    parser_used = f"{parser_used}+llm"
                    logger.info("llm_extraction_enriched", document_id=str(document.id), document_type=document_type, fields_added=len(llm_fields))
            except Exception as e:
                logger.warning("llm_enrichment_failed", document_id=str(document.id), error=str(e))

        logger.debug(
            "parser_selected",
            document_id=str(document.id),
            document_type=document_type,
            file_format=file_format,
            parser=parser_used,
        )

    except Exception as e:
        logger.exception(
            "extraction_failed_fallback",
            document_id=str(document.id),
            document_type=document_type,
            error=str(e),
        )
        parsed_data = parse_by_document_type(document_type, "", None)
        raw_result = None

    confidence = _domain_compute_confidence(document_type, parsed_data, raw_result, confidence_scorer)
    return _build_extraction_result(document_type, file_path, parsed_data, confidence)


def _build_extraction_result(
    document_type: str,
    file_path: Path,
    parsed_data: dict,
    confidence: ExtractionScore,
) -> dict:
    """Build the structured extraction result dict."""
    return {
        "document_type": document_type,
        "file_path": str(file_path),
        "confidence": confidence.overall_confidence,
        "fields_extracted": len(parsed_data),
        "raw_text_length": len(str(parsed_data)),
        "extracted_fields": parsed_data,
        "confidence_score": {
            "overall_confidence": confidence.overall_confidence,
            "routing_decision": confidence.routing_decision,
            "field_confidences": confidence.field_confidences,
            "low_confidence_fields": confidence.low_confidence_fields,
        },
    }


async def persist_results(state: dict[str, Any]) -> None:
    """Persist extraction and validation results to PostgreSQL, Qdrant, and Neo4j.

    This is the service-layer persistence step that replaces inline DB calls
    in the processing node. All I/O (PostgreSQL, Qdrant, Neo4j) lives here.
    """
    start_ms = time.perf_counter()
    application_id = state.get("application_id")
    applicant_id = state.get("applicant_id")
    extraction_results = state.get("extraction_results", [])
    support_category = state.get("applicant_info", {}).get("support_category", "")

    logger.info(
        "persist_start",
        application_id=application_id,
        applicant_id=applicant_id,
        document_count=len(extraction_results),
    )

    # PostgreSQL: store extraction data and cross-validation results
    try:
        db = await get_session(settings)
        async with db:
            for er in extraction_results:
                if er.get("status") == "success" and er.get("document_id"):
                    try:
                        await store_extraction_data(
                            er.get("document_type", "unknown"),
                            _UUID(er["document_id"]) if isinstance(er["document_id"], str) else er["document_id"],
                            er,
                            EmiratesIDRepository(db),
                            BankStatementRepository(db),
                            CreditReportRepository(db),
                            ResumeRepository(db),
                            AssetsLiabilitiesRepository(db),
                            ApplicationFormRepository(db),
                        )
                    except Exception as e:
                        logger.warning(
                            "persist_store_extraction_failed",
                            document_id=er.get("document_id"),
                            error=str(e),
                        )
            try:
                await ValidationService(db).validate_cross_document(
                    applicant_id=_UUID(applicant_id) if applicant_id else uuid4(),
                    support_category=support_category or None,
                )
            except Exception as e:
                logger.warning(
                    "persist_cross_validation_failed",
                    error=str(e),
                )
    except Exception as e:
        logger.warning("persist_postgresql_failed", error=str(e))

    # Qdrant: upsert document embeddings
    try:
        q = get_qdrant_client(settings)
        es = DocumentEmbeddingStore(q)
        for er in extraction_results:
            if er.get("status") == "success" and er.get("document_id"):
                try:
                    await es.upsert(
                        point_id=str(uuid4()),
                        vector=[0.0] * 768,
                        applicant_id=applicant_id or "unknown",
                        document_type=er.get("document_type", "unknown"),
                        document_id=str(er["document_id"]),
                    )
                except Exception as e:
                    logger.warning(
                        "persist_embedding_upsert_failed",
                        document_id=er.get("document_id"),
                        error=str(e),
                    )
    except Exception as e:
        logger.warning("persist_qdrant_failed", error=str(e))

    # Neo4j: link documents to applicant in lineage graph
    try:
        n = get_neo4j_driver(settings)
        lr = DocumentLineageRepository(n)
        for er in extraction_results:
            if er.get("status") == "success" and er.get("document_id"):
                try:
                    await lr.link_document_to_applicant(
                        applicant_id=_UUID(applicant_id) if applicant_id else uuid4(),
                        document=DocumentNode(
                            id=_UUID(str(er["document_id"])),
                            document_type=er.get("document_type", "unknown"),
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        "persist_lineage_link_failed",
                        document_id=er.get("document_id"),
                        error=str(e),
                    )
    except Exception as e:
        logger.warning("persist_neo4j_failed", error=str(e))

    duration_ms = (time.perf_counter() - start_ms) * 1000
    logger.info(
        "persist_complete",
        application_id=application_id,
        applicant_id=applicant_id,
        duration_ms=round(duration_ms, 2),
        document_count=len(extraction_results),
    )
