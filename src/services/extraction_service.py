"""Extraction service - orchestrate document data extraction pipeline."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from langfuse import observe
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.constants.document_types import DEFAULT_REQUIRED_DOCUMENTS, REQUIRED_DOCUMENTS
from src.infrastructure.db.repositories.document_repo import DocumentRepository
from src.infrastructure.document_processing.ocr import OCREngine
from src.infrastructure.document_processing.pdf_parser import PDFParser
from src.infrastructure.document_processing.resume_parser import ResumeParser
from src.infrastructure.document_processing.xlsx_extractor import XLSXExtractor
from src.infrastructure.db.repositories.extraction_repo import (
    ApplicationFormRepository,
    AssetsLiabilitiesRepository,
    BankStatementRepository,
    CreditReportRepository,
    EmiratesIDRepository,
    ResumeRepository,
)
from src.infrastructure.extraction_persistence import (
    create_embedding,
    create_lineage,
    store_extraction_data,
)
from src.services.extraction_pipeline import run_extraction_pipeline

logger = structlog.get_logger(__name__)


class ExtractionService:
    """Orchestrate document extraction, embedding, and lineage tracking."""

    def __init__(
        self,
        session: AsyncSession,
        neo4j_driver=None,
        qdrant_client=None,
        llm_client=None,
        confidence_scorer=None,
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
        self.llm_client = llm_client
        self._confidence_scorer = confidence_scorer
        self.pdf_parser = PDFParser()
        self.ocr_engine = OCREngine()
        self.xlsx_extractor = XLSXExtractor()
        self.resume_parser = ResumeParser()

    @observe(as_type="generation", name="extract_document")
    async def extract_document(self, document_id: UUID) -> dict:
        """Extract data from a single document and store results."""
        start = datetime.now(timezone.utc)
        document = await self.doc_repo.get_by_id(document_id)
        if document is None:
            logger.warning("document_not_found", document_id=str(document_id))
            raise ValueError(f"Document {document_id} not found")

        await self.doc_repo.update_status(document_id, processing_status="extracting")

        try:
            extraction_result = await run_extraction_pipeline(
                document,
                pdf_parser=self.pdf_parser,
                ocr_engine=self.ocr_engine,
                xlsx_extractor=self.xlsx_extractor,
                resume_parser=self.resume_parser,
                llm_client=self.llm_client,
                confidence_scorer=self._confidence_scorer,
            )

            await store_extraction_data(
                document.document_type, document_id, extraction_result,
                self.emirates_id_repo, self.bank_stmt_repo,
                self.credit_report_repo, self.resume_repo,
                self.assets_liabilities_repo, self.application_form_repo,
            )

            await self.doc_repo.update_status(
                document_id, processing_status="completed", extraction_status="success",
            )

            if document.overall_confidence is None:
                document.overall_confidence = extraction_result.get("confidence", 0.0)
                await self.doc_repo.update(document)

            await create_lineage(document, self.neo4j_driver)
            await create_embedding(document, extraction_result, self.qdrant_client)

            duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            logger.info(
                "document_extracted",
                document_id=str(document_id),
                document_type=document.document_type,
                confidence=extraction_result.get("confidence"),
                duration_ms=round(duration_ms, 2),
            )
            return extraction_result

        except Exception as e:
            await self.doc_repo.update_status(
                document_id, processing_status="failed", extraction_status="failed",
            )
            document.error_log = str(e)
            await self.doc_repo.update(document)
            logger.exception("document_extraction_failed", document_id=str(document_id), error=str(e))
            raise

    async def extract_all_documents(self, applicant_id: UUID) -> list[dict]:
        """Extract all uploaded documents for an applicant."""
        start = datetime.now(timezone.utc)
        documents = await self.doc_repo.get_by_applicant(applicant_id)
        results = []
        for doc in documents:
            if doc.processing_status in ("uploaded", "failed"):
                try:
                    result = await self.extract_document(doc.id)
                    results.append({"document_id": str(doc.id), "status": "success", **result})
                except Exception as e:
                    logger.exception("document_extraction_failed", document_id=str(doc.id), error=str(e))
                    results.append({"document_id": str(doc.id), "status": "failed", "error": str(e)})
        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        logger.info(
            "all_documents_extracted",
            applicant_id=str(applicant_id),
            total=len(documents),
            processed=len(results),
            successes=sum(1 for r in results if r["status"] == "success"),
            failures=sum(1 for r in results if r["status"] == "failed"),
            duration_ms=round(duration_ms, 2),
        )
        return results

    def get_required_documents(self, support_category: str | None) -> list[str]:
        """Get list of required documents for a support category."""
        if support_category is None:
            return DEFAULT_REQUIRED_DOCUMENTS
        return REQUIRED_DOCUMENTS.get(support_category.lower(), DEFAULT_REQUIRED_DOCUMENTS)
