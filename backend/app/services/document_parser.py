import io
from typing import List, Dict, Any, Optional
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class ParsedPage:
    def __init__(self, page_number: int, text: str, heading: Optional[str] = None):
        self.page_number = page_number
        self.text = text.strip()
        self.heading = heading


class DocumentParserService:
    def parse(self, file_bytes: bytes, file_type: str) -> List[ParsedPage]:
        f_type = file_type.lower().strip(".")
        if f_type == "pdf":
            return self._parse_pdf(file_bytes)
        elif f_type == "docx":
            return self._parse_docx(file_bytes)
        elif f_type == "pptx":
            return self._parse_pptx(file_bytes)
        elif f_type == "txt":
            return self._parse_txt(file_bytes)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _parse_pdf(self, file_bytes: bytes) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text") or ""
                if text.strip():
                    # Attempt to extract top header line as page heading
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    heading = lines[0] if lines and len(lines[0]) < 80 else None
                    pages.append(ParsedPage(page_number=page_idx + 1, text=text, heading=heading))
            doc.close()
        except ImportError:
            logger.warning("PyMuPDF (fitz) not available. Falling back to plain text extraction.")
            text = file_bytes.decode("utf-8", errors="ignore")
            pages.append(ParsedPage(page_number=1, text=text))
        except Exception as e:
            logger.error(f"Failed to parse PDF file: {e}")
            raise ValueError(f"Failed to extract text from PDF: {e}")

        if not pages:
            pages.append(ParsedPage(page_number=1, text="[Empty Document]"))
        return pages

    def _parse_docx(self, file_bytes: bytes) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            full_text_blocks = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text_blocks.append(para.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        full_text_blocks.append(row_text)

            combined_text = "\n\n".join(full_text_blocks)
            # Estimate 500 words per page for DOCX
            words = combined_text.split()
            page_size = 400
            for i in range(0, max(len(words), 1), page_size):
                page_words = words[i : i + page_size]
                page_text = " ".join(page_words)
                if page_text.strip():
                    pages.append(ParsedPage(page_number=(i // page_size) + 1, text=page_text))
        except Exception as e:
            logger.error(f"Failed to parse DOCX: {e}")
            raise ValueError(f"Failed to parse DOCX document: {e}")

        if not pages:
            pages.append(ParsedPage(page_number=1, text="[Empty Document]"))
        return pages

    def _parse_pptx(self, file_bytes: bytes) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        try:
            from pptx import Presentation
            prs = Presentation(io.BytesIO(file_bytes))
            for idx, slide in enumerate(prs.slides):
                slide_texts = []
                heading = None
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            t = paragraph.text.strip()
                            if t:
                                if not heading:
                                    heading = t[:80]
                                slide_texts.append(t)
                text = "\n".join(slide_texts)
                if text.strip():
                    pages.append(ParsedPage(page_number=idx + 1, text=text, heading=heading))
        except Exception as e:
            logger.error(f"Failed to parse PPTX: {e}")
            raise ValueError(f"Failed to parse presentation: {e}")

        if not pages:
            pages.append(ParsedPage(page_number=1, text="[Empty Document]"))
        return pages

    def _parse_txt(self, file_bytes: bytes) -> List[ParsedPage]:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="ignore")

        # Split text into ~2000 character pages
        page_size = 2000
        pages: List[ParsedPage] = []
        for i in range(0, max(len(text), 1), page_size):
            chunk = text[i : i + page_size]
            if chunk.strip():
                pages.append(ParsedPage(page_number=(i // page_size) + 1, text=chunk))

        if not pages:
            pages.append(ParsedPage(page_number=1, text="[Empty Document]"))
        return pages


document_parser = DocumentParserService()
