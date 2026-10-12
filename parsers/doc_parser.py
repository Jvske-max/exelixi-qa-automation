"""Unified document parser interface dispatching based on file extension."""

from __future__ import annotations

from pathlib import Path

from parsers.docx_parser import DocxParser
from parsers.models import TestCase
from parsers.pdf_parser import PdfParser


class DocParser:
    """Unified document parser for test specifications (.docx and .pdf)."""

    @classmethod
    def parse(cls, file_path: str | Path) -> TestCase:
        """Parse a test specification file (.docx or .pdf) into a TestCase model."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".docx":
            return DocxParser.parse(path)
        elif ext == ".pdf":
            return PdfParser.parse(path)
        else:
            raise ValueError(
                f"Unsupported file format '{ext}' for file '{path.name}'. Supported formats: .docx, .pdf"
            )
