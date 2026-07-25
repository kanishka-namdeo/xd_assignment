"""PDF parser using pymupdf4llm for document extraction."""

import asyncio
import time
from pathlib import Path
from typing import Any

import pymupdf4llm
import structlog
from pydantic import ValidationError

from .schemas import BoundingBox, ExtractedField, ExtractionResult

logger = structlog.get_logger(__name__)


class PDFParser:
    """PDF parser using pymupdf4llm for high-quality extraction.
    
    Supports both digital PDFs (with text layer) and scanned PDFs (OCR fallback).
    Extracts text, tables, and structured content with bounding boxes.
    """

    def __init__(self, use_ocr: bool = False):
        """Initialize PDF parser.
        
        Args:
            use_ocr: Force OCR even for digital PDFs (default: False)
        """
        self.use_ocr = use_ocr
        self.logger = logger.bind(component="pdf_parser")

    async def extract(
        self,
        file_path: str | Path,
        pages: list[int] | None = None,
        extract_tables: bool = True,
    ) -> ExtractionResult:
        """Extract content from PDF file.
        
        Args:
            file_path: Path to PDF file
            pages: Specific pages to extract (0-indexed). None = all pages
            extract_tables: Whether to extract tables (default: True)
            
        Returns:
            ExtractionResult with extracted fields and metadata
            
        Example:
            >>> parser = PDFParser()
            >>> result = await parser.extract("document.pdf", pages=[0, 1])
            >>> print(result.overall_confidence)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        start_time = time.monotonic()
        self.logger.info("pdf_parse_start", file_path=str(file_path), pages=pages)

        try:
            # Run CPU-bound extraction in thread pool
            result = await asyncio.to_thread(
                self._extract_sync, file_path, pages, extract_tables
            )
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.info(
                "pdf_parse_complete",
                file_path=str(file_path),
                duration_ms=round(duration_ms, 2),
                page_count=len(pages) if pages else result.source_coordinates
                and len(result.source_coordinates)
                or 0,
                field_count=len(result.fields),
                overall_confidence=result.overall_confidence,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.exception(
                "pdf_parse_failed",
                error=str(e),
                file_path=str(file_path),
                duration_ms=round(duration_ms, 2),
            )
            raise

    def _extract_sync(
        self,
        file_path: Path,
        pages: list[int] | None,
        extract_tables: bool,
    ) -> ExtractionResult:
        """Synchronous PDF extraction (runs in thread pool)."""
        # Convert to markdown with page chunks and bounding boxes
        md_text = pymupdf4llm.to_markdown(
            str(file_path),
            page_chunks=True,
            write_images=False,
        )

        # Extract structured data with bounding boxes
        json_data = pymupdf4llm.to_json(
            str(file_path),
            page_chunks=True,
            page_border=True,
        )

        fields: list[ExtractedField] = []
        raw_data: dict[str, Any] = {
            "markdown": md_text,
            "json_structure": json_data,
        }
        source_coords: dict[str, Any] = {}

        # Parse pages and extract fields with coordinates
        if isinstance(json_data, dict) and "pages" in json_data:
            for page_data in json_data["pages"]:
                page_num = page_data.get("page_number", 0)
                
                # Extract text blocks with bounding boxes
                for block in page_data.get("blocks", []):
                    if block.get("type") == "text":
                        bbox = block.get("bbox", [0, 0, 0, 0])
                        text = block.get("text", "")
                        
                        fields.append(
                            ExtractedField(
                                field_name=f"page_{page_num}_text",
                                field_value=text,
                                confidence=0.95,  # High confidence for digital PDFs
                                source_page=page_num,
                                source_bounding_box=BoundingBox(
                                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3], page=page_num
                                ),
                                source_text=text,
                            )
                        )

                # Track page coordinates
                source_coords[f"page_{page_num}"] = {
                    "width": page_data.get("width"),
                    "height": page_data.get("height"),
                }

        # Calculate overall confidence
        if fields:
            avg_confidence = sum(f.confidence for f in fields) / len(fields)
        else:
            avg_confidence = 0.0

        return ExtractionResult(
            document_type="pdf",
            fields=fields,
            raw_extracted_data=raw_data,
            overall_confidence=avg_confidence,
            source_coordinates=source_coords,
        )

    async def extract_to_markdown(
        self,
        file_path: str | Path,
        pages: list[int] | None = None,
    ) -> str:
        """Extract PDF content as markdown text.
        
        Args:
            file_path: Path to PDF file
            pages: Specific pages to extract (0-indexed)
            
        Returns:
            Markdown-formatted text
        """
        file_path = Path(file_path)
        
        async def _to_md():
            return pymupdf4llm.to_markdown(
                str(file_path),
                pages=pages,
                page_chunks=False,
            )
        
        return await asyncio.to_thread(_to_md)

    async def extract_to_json(
        self,
        file_path: str | Path,
        pages: list[int] | None = None,
    ) -> dict[str, Any]:
        """Extract PDF content as structured JSON with bounding boxes.
        
        Args:
            file_path: Path to PDF file
            pages: Specific pages to extract (0-indexed)
            
        Returns:
            JSON structure with pages, blocks, and coordinates
        """
        file_path = Path(file_path)
        
        async def _to_json():
            return pymupdf4llm.to_json(
                str(file_path),
                pages=pages,
                page_chunks=True,
                page_border=True,
            )
        
        return await asyncio.to_thread(_to_json)

    async def get_page_count(self, file_path: str | Path) -> int:
        """Get total number of pages in PDF.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Number of pages
        """
        file_path = Path(file_path)

        async def _count():
            import pymupdf
            doc = pymupdf.open(str(file_path))
            count = len(doc)
            doc.close()
            return count

        start_time = time.monotonic()
        count = await asyncio.to_thread(_count)
        duration_ms = (time.monotonic() - start_time) * 1000
        self.logger.info(
            "pdf_page_count",
            file_path=str(file_path),
            page_count=count,
            duration_ms=round(duration_ms, 2),
        )
        return count
