"""
OCR for scanned PDFs.

Pages that contain no extractable text (scans, photos of notes) are rendered to images and
transcribed with Gemini's vision model. Only text-less pages are sent, and at most
OCR_MAX_PAGES per document, so typed PDFs never pay this cost.
"""
import asyncio
from typing import List, Set

from backend.app.core.logging import get_logger
from backend.app.services.document_parser import ParsedPage, document_parser

logger = get_logger(__name__)

OCR_MAX_PAGES = 25
OCR_CONCURRENCY = 3
_MIN_TEXT_CHARS = 25

OCR_PROMPT = (
    "Transcribe all readable text on this page of study notes exactly as written, in reading order. "
    "Keep headings on their own lines. Write tables as simple rows. Do not add commentary, summaries "
    "or text that is not on the page. If the page has no readable text, reply with an empty response."
)


def ocr_available() -> bool:
    from backend.app.ai.gateway import ai_gateway

    gemini = ai_gateway.get_provider("gemini")
    return bool(gemini and gemini.is_configured())


def pdf_page_count(file_bytes: bytes) -> int:
    try:
        import fitz

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return len(doc)
    except Exception:
        return 0


def pages_needing_ocr(parsed: List[ParsedPage], total_pages: int) -> List[int]:
    have_text: Set[int] = {p.page_number for p in parsed if len((p.text or "").strip()) >= _MIN_TEXT_CHARS}
    return [n for n in range(1, total_pages + 1) if n not in have_text]


async def ocr_pages(file_bytes: bytes, page_numbers: List[int]) -> List[ParsedPage]:
    """Transcribes the given pages; pages that fail or come back empty are skipped."""
    from backend.app.ai.gateway import ai_gateway
    from backend.app.ai.types import AIRequest, TaskType

    semaphore = asyncio.Semaphore(OCR_CONCURRENCY)

    async def _one(page_number: int):
        async with semaphore:
            png = await asyncio.to_thread(document_parser.render_page_image, file_bytes, page_number, 150)
            if not png:
                return None
            try:
                res = await ai_gateway.generate_text(
                    AIRequest(prompt=OCR_PROMPT, images=[png], task_type=TaskType.GENERAL, temperature=0.0)
                )
            except Exception as e:
                logger.warning(f"OCR failed for page {page_number}: {e}")
                return None
            text = (getattr(res, "content", "") or "").strip()
            if len(text) < _MIN_TEXT_CHARS:
                return None
            first_line = next((ln.strip(" #*") for ln in text.splitlines() if ln.strip()), "")
            heading = first_line if 3 <= len(first_line) <= 90 else None
            return ParsedPage(page_number=page_number, text=text, heading=heading,
                              section_breadcrumbs=[heading] if heading else [])

    results = await asyncio.gather(*(_one(n) for n in page_numbers[:OCR_MAX_PAGES]))
    return [p for p in results if p is not None]
