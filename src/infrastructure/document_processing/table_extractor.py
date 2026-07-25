"""Table extractor using camelot-py for PDF table extraction."""

import asyncio
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from .schemas import TableExtractionResult

logger = structlog.get_logger()


class TableExtractor:
    """Table extractor using camelot-py for PDF tables.
    
    Supports automatic flavor detection (lattice for ruled tables,
    network for borderless tables). Returns DataFrames with extracted data.
    """

    def __init__(self, flavor: str = "auto"):
        """Initialize table extractor.
        
        Args:
            flavor: Table detection flavor - "auto", "lattice", "stream", or "network"
        """
        self.flavor = flavor
        self.logger = logger.bind(component="table_extractor")

    async def extract(
        self,
        file_path: str | Path,
        pages: str = "all",
        table_areas: list[tuple[float, float, float, float]] | None = None,
    ) -> TableExtractionResult:
        """Extract tables from PDF file.
        
        Args:
            file_path: Path to PDF file
            pages: Page specification (e.g., "1,2,3" or "all")
            table_areas: Specific table regions [(x0, y0, x1, y1), ...]
            
        Returns:
            TableExtractionResult with extracted tables as DataFrames
            
        Example:
            >>> extractor = TableExtractor(flavor="auto")
            >>> result = await extractor.extract("bank_statement.pdf", pages="1,2")
            >>> for table_df in result.tables:
            ...     print(table_df.head())
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.logger.info(
            "extracting_tables",
            file_path=str(file_path),
            pages=pages,
            flavor=self.flavor,
        )

        try:
            result = await asyncio.to_thread(
                self._extract_sync, file_path, pages, table_areas
            )
            return result
        except Exception as e:
            self.logger.error("table_extraction_failed", error=str(e), file_path=str(file_path))
            raise

    def _extract_sync(
        self,
        file_path: Path,
        pages: str,
        table_areas: list[tuple[float, float, float, float]] | None,
    ) -> TableExtractionResult:
        """Synchronous table extraction (runs in thread pool)."""
        import camelot

        # Build extraction parameters
        kwargs: dict[str, Any] = {
            "pages": pages,
        }

        if self.flavor != "auto":
            kwargs["flavor"] = self.flavor
        else:
            # Auto-detect: try lattice first, then network
            kwargs["flavor"] = "lattice"

        if table_areas:
            kwargs["table_areas"] = table_areas

        # Extract tables
        tables = camelot.read_pdf(str(file_path), **kwargs)

        # If auto mode and no tables found with lattice, try network
        if self.flavor == "auto" and len(tables) == 0:
            self.logger.info("retrying_with_network_flavor", file_path=str(file_path))
            kwargs["flavor"] = "network"
            tables = camelot.read_pdf(str(file_path), **kwargs)

        # Convert to list of DataFrames
        table_dfs: list[pd.DataFrame] = []
        confidences: list[float] = []

        for table in tables:
            table_dfs.append(table.df)
            confidences.append(table.accuracy / 100.0)  # Convert percentage to 0-1

        # Calculate overall confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return TableExtractionResult(
            tables=table_dfs,
            table_count=len(table_dfs),
            flavor=self.flavor,
            confidence=avg_confidence,
        )

    async def extract_to_dataframes(
        self,
        file_path: str | Path,
        pages: str = "all",
    ) -> list[pd.DataFrame]:
        """Extract tables as pandas DataFrames.
        
        Args:
            file_path: Path to PDF file
            pages: Page specification
            
        Returns:
            List of DataFrames, one per table
        """
        result = await self.extract(file_path, pages)
        return result.tables

    async def get_table_count(
        self,
        file_path: str | Path,
        pages: str = "all",
    ) -> int:
        """Get number of tables in PDF.
        
        Args:
            file_path: Path to PDF file
            pages: Page specification
            
        Returns:
            Number of tables detected
        """
        result = await self.extract(file_path, pages)
        return result.table_count
