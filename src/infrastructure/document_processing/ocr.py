"""OCR engine using PaddleOCR for image text extraction."""

import asyncio
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from .schemas import OCRResult

logger = structlog.get_logger()


class OCREngine:
    """OCR engine using PaddleOCR for multilingual text extraction.
    
    Supports Arabic + English with GPU acceleration option.
    Returns text with bounding boxes and confidence scores.
    """

    def __init__(
        self,
        language: str = "ar+en",
        use_gpu: bool = False,
        enable_hpi: bool = True,
    ):
        """Initialize OCR engine.
        
        Args:
            language: Language codes (default: "ar+en" for Arabic + English)
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
            
            self._ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang=self.language,
                use_gpu=self.use_gpu,
                enable_hpi=self.enable_hpi,
                show_log=False,
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

        self.logger.info("extracting_ocr", image_path=str(image_path), language=self.language)

        try:
            result = await asyncio.to_thread(
                self._extract_sync, image_path, detect_orientation
            )
            return result
        except Exception as e:
            self.logger.error("ocr_extraction_failed", error=str(e), image_path=str(image_path))
            raise

    def _extract_sync(
        self,
        image_path: Path,
        detect_orientation: bool,
    ) -> OCRResult:
        """Synchronous OCR extraction (runs in thread pool)."""
        ocr = self._get_ocr()
        
        # Run OCR
        ocr_result = ocr.ocr(
            str(image_path),
            cls=detect_orientation,
        )

        # Parse PaddleOCR output format
        blocks: list[dict[str, Any]] = []
        all_text_parts: list[str] = []
        confidences: list[float] = []

        if ocr_result and len(ocr_result) > 0:
            for line_group in ocr_result:
                if not line_group:
                    continue
                    
                for line in line_group:
                    # PaddleOCR format: [bbox, (text, confidence)]
                    bbox_coords = line[0]  # [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
                    text = line[1][0]
                    confidence = line[1][1]

                    # Convert to bounding box format
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
