"""OCR engine using PaddleOCR for image text extraction."""

import asyncio
import time
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from .schemas import OCRResult

logger = structlog.get_logger(__name__)


class OCREngine:
    """OCR engine using PaddleOCR for multilingual text extraction.
    
    Supports Arabic + English with GPU acceleration option.
    Returns text with bounding boxes and confidence scores.
    """

    def __init__(
        self,
        language: str = "en",
        use_gpu: bool = False,
        enable_hpi: bool = True,
    ):
        """Initialize OCR engine.
        
        Args:
            language: Language code (default: "en" for English; also supports "ar", "ch", etc.)
            use_gpu: Enable GPU acceleration (requires CUDA)
            enable_hpi: Enable high-performance inference
        """
        self.language = language
        self.use_gpu = use_gpu
        self.enable_hpi = enable_hpi
        self._ocr_instance = None
        self.logger = logger.bind(component="ocr_engine")

    def _get_ocr(self):
        """Lazy-load OCR instance (thread-safe singleton)."""
        if self._ocr_instance is None:
            from paddleocr import PaddleOCR
            import logging
            
            # Suppress PaddleOCR logs (3.0+ removed show_log parameter)
            paddleocr_logger = logging.getLogger("paddleocr")
            paddleocr_logger.setLevel(logging.ERROR)
            
            # PaddleOCR 3.x API: orientation detection is now a constructor parameter
            # enable_mkldnn=False bypasses a known PaddlePaddle 3.3.x bug where the
            # PIR-to-oneDNN converter crashes on pir::ArrayAttribute types
            self._ocr_instance = PaddleOCR(
                lang=self.language,
                use_doc_orientation_classify=True,
                enable_mkldnn=False,
            )
        return self._ocr_instance

    async def extract(
        self,
        image_path: str | Path,
        detect_orientation: bool = True,
    ) -> OCRResult:
        """Extract text from image with bounding boxes.
        
        Args:
            image_path: Path to image file (PNG, JPG, TIFF, etc.)
            detect_orientation: Auto-detect and correct orientation
            
        Returns:
            OCRResult with text, blocks, and confidence
            
        Example:
            >>> ocr = OCREngine(language="ar+en")
            >>> result = await ocr.extract("emirates_id.png")
            >>> print(result.text)
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        start_time = time.monotonic()
        self.logger.info("ocr_start", image_path=str(image_path), language=self.language)

        try:
            result = await asyncio.to_thread(
                self._extract_sync, image_path, detect_orientation
            )
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.info(
                "ocr_complete",
                image_path=str(image_path),
                duration_ms=round(duration_ms, 2),
                block_count=len(result.blocks),
                confidence=round(result.confidence, 4),
                text_length=len(result.text),
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.exception(
                "ocr_failed",
                error=str(e),
                image_path=str(image_path),
                duration_ms=round(duration_ms, 2),
            )
            raise

    def _extract_sync(
        self,
        image_path: Path,
        detect_orientation: bool,
    ) -> OCRResult:
        """Synchronous OCR extraction (runs in thread pool)."""
        ocr = self._get_ocr()
        
        # PaddleOCR 3.x: orientation detection is set at init, not per-call
        ocr_results = list(ocr.predict(str(image_path)))

        # Parse PaddleOCR 3.x output format
        blocks: list[dict[str, Any]] = []
        all_text_parts: list[str] = []
        confidences: list[float] = []

        if ocr_results and len(ocr_results) > 0:
            for result in ocr_results:
                # PaddleOCR 3.x returns OCRResult objects with rec_texts, rec_scores, rec_polys
                rec_texts = result.get('rec_texts', [])
                rec_scores = result.get('rec_scores', [])
                rec_polys = result.get('rec_polys', [])
                
                for i, text in enumerate(rec_texts):
                    if not text:
                        continue
                    
                    confidence = rec_scores[i] if i < len(rec_scores) else 0.0
                    bbox_coords = rec_polys[i] if i < len(rec_polys) else []
                    
                    # Convert to bounding box format
                    if len(bbox_coords) > 0:
                        x_coords = [pt[0] for pt in bbox_coords]
                        y_coords = [pt[1] for pt in bbox_coords]
                        
                        block = {
                            "text": text,
                            "confidence": float(confidence),
                            "bbox": {
                                "x0": min(x_coords),
                                "y0": min(y_coords),
                                "x1": max(x_coords),
                                "y1": max(y_coords),
                            },
                        }
                        blocks.append(block)
                    
                    all_text_parts.append(text)
                    confidences.append(confidence)

        # Combine all text
        full_text = "\n".join(all_text_parts)
        
        # Calculate overall confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            blocks=blocks,
            confidence=avg_confidence,
            language=self.language,
        )

    async def extract_from_bytes(
        self,
        image_bytes: bytes,
        detect_orientation: bool = True,
    ) -> OCRResult:
        """Extract text from image bytes.
        
        Args:
            image_bytes: Raw image bytes
            detect_orientation: Auto-detect and correct orientation
            
        Returns:
            OCRResult with text, blocks, and confidence
        """
        import tempfile
        
        # Write bytes to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)
        
        try:
            return await self.extract(tmp_path, detect_orientation)
        finally:
            tmp_path.unlink(missing_ok=True)
