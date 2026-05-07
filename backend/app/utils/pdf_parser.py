"""PDF parsing helpers with per-page OCR fallback."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

try:
    import fitz

    PYMUPDF_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    fitz = None
    PYMUPDF_AVAILABLE = False

try:
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    RAPIDOCR_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    np = None
    RapidOCR = None
    RAPIDOCR_AVAILABLE = False


class PDFParser:
    """Parse PDFs with pdfplumber first and OCR fallback for sparse pages."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self._ocr_engine = None
        logger.info(f"Loading PDF: {self.pdf_path.name}")

    def parse(self, pages: Optional[str] = None) -> List[Dict]:
        chunks: list[dict] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"PDF total pages: {total_pages}")

            page_indices = self._parse_page_range(pages, total_pages)
            logger.info(f"Processing pages: {len(page_indices)}")

            for i in page_indices:
                page = pdf.pages[i]
                pdf_text = self._extract_page_text_with_pdfplumber(page)
                final_text = pdf_text
                extract_method = "pdfplumber"

                if self._should_use_ocr(pdf_text):
                    ocr_text = self._extract_page_text_with_ocr(i)
                    final_text, extract_method = self._select_page_text(pdf_text, ocr_text)

                if len(final_text.strip()) < 50:
                    logger.debug(f"Skip sparse page: {i + 1}")
                    continue

                text_truncated = final_text[: settings.MAX_TEXT_LENGTH]
                chunks.append(
                    {
                        "page": i + 1,
                        "content": text_truncated,
                        "extract_method": extract_method,
                    }
                )

                logger.debug(
                    f"Page {i + 1}: chars={len(text_truncated)} method={extract_method}"
                )

        logger.success(f"Parsed {len(chunks)} effective pages")
        return chunks

    def _extract_page_text_with_pdfplumber(self, page) -> str:
        text = page.extract_text() or ""
        try:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        row_text = "\t".join(str(cell) if cell else "" for cell in row)
                        text += "\n" + row_text
        except Exception as exc:
            logger.warning(f"Table extraction failed on page {page.page_number}: {exc}")
        return self._normalize_text(text)

    def _should_use_ocr(self, text: str) -> bool:
        if not settings.ENABLE_PDF_OCR_FALLBACK:
            return False
        if not RAPIDOCR_AVAILABLE or not PYMUPDF_AVAILABLE:
            return False
        return self._effective_char_count(text) < settings.PDF_OCR_MIN_CHARS

    def _effective_char_count(self, text: str) -> int:
        cleaned = re.sub(r"\s+", "", text or "")
        return len(cleaned)

    def _extract_page_text_with_ocr(self, page_index: int) -> str:
        engine = self._get_ocr_engine()
        if engine is None or fitz is None or np is None:
            return ""

        doc = None
        try:
            doc = fitz.open(self.pdf_path)
            page = doc.load_page(page_index)
            matrix = fitz.Matrix(settings.PDF_OCR_DPI / 72.0, settings.PDF_OCR_DPI / 72.0)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            result, _ = engine(image)
            if not result:
                return ""
            lines = []
            for item in result:
                if len(item) < 2:
                    continue
                line = str(item[1]).strip()
                if line:
                    lines.append(line)
            return self._normalize_text("\n".join(lines))
        except Exception as exc:
            logger.warning(f"OCR failed on page {page_index + 1}: {exc}")
            return ""
        finally:
            if doc is not None:
                doc.close()

    def _get_ocr_engine(self):
        if not RAPIDOCR_AVAILABLE:
            return None
        if self._ocr_engine is None:
            self._ocr_engine = RapidOCR()
        return self._ocr_engine

    def _select_page_text(self, pdf_text: str, ocr_text: str) -> tuple[str, str]:
        pdf_text = self._normalize_text(pdf_text)
        ocr_text = self._normalize_text(ocr_text)

        if not ocr_text:
            return pdf_text, "pdfplumber"
        if not pdf_text:
            return ocr_text, "ocr"

        pdf_count = self._effective_char_count(pdf_text)
        ocr_count = self._effective_char_count(ocr_text)

        if ocr_count >= pdf_count * 1.2:
            return ocr_text, "ocr"

        merged_lines: list[str] = []
        seen: set[str] = set()
        for source in (pdf_text, ocr_text):
            for line in source.splitlines():
                cleaned = line.strip()
                if not cleaned:
                    continue
                key = re.sub(r"\s+", " ", cleaned)
                if key in seen:
                    continue
                seen.add(key)
                merged_lines.append(cleaned)
        return "\n".join(merged_lines), "merged"

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = (text or "").replace("\x00", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _parse_page_range(pages: Optional[str], total_pages: int) -> List[int]:
        if not pages:
            return list(range(total_pages))

        try:
            if "-" in pages:
                start, end = map(int, pages.split("-"))
                return list(range(start - 1, min(end, total_pages)))
            page_list = [int(p.strip()) - 1 for p in pages.split(",")]
            return [p for p in page_list if 0 <= p < total_pages]
        except ValueError:
            logger.warning(f"Invalid page range '{pages}', falling back to all pages")
            return list(range(total_pages))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <pdf_path> [pages]")
        raise SystemExit(1)

    parser = PDFParser(sys.argv[1])
    chunks = parser.parse(pages=sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"Parsed pages: {len(chunks)}")
    for chunk in chunks[:3]:
        print(f"\nPage {chunk['page']} ({chunk.get('extract_method')}):")
        print(chunk["content"][:200])
