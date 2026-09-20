import re
import uuid
from typing import List, Dict, Any, Optional
from backend.app.services.document_parser import ParsedPage
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentChunkResult:
    def __init__(
        self,
        id: str,
        workspace_id: str,
        document_id: str,
        chunk_index: int,
        page_number: int,
        heading: Optional[str],
        text: str,
        token_count: int,
        metadata: Dict[str, Any],
    ):
        self.id = id
        self.workspace_id = workspace_id
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.heading = heading
        self.text = text
        self.token_count = token_count
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "heading": self.heading,
            "text": self.text,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


class SemanticChunkerService:
    def __init__(
        self,
        target_chunk_size: int = settings.chunk_size_chars,
        overlap_size: int = settings.chunk_overlap_chars,
    ):
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def _split_into_sentences(self, text: str) -> List[str]:
        # Split text into sentences using regex lookbehind
        sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
        return sentences if sentences else [text]

    def chunk_pages(
        self,
        workspace_id: str,
        document_id: str,
        pages: List[ParsedPage],
        document_title: str = "",
        source_filename: str = "",
    ) -> List[DocumentChunkResult]:
        chunks: List[DocumentChunkResult] = []
        global_chunk_idx = 0

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            current_heading = page.heading
            current_breadcrumbs = getattr(page, "section_breadcrumbs", []) or ([current_heading] if current_heading else [])

            # Split page into structural blocks: paragraphs or tables
            raw_blocks = [b.strip() for b in page_text.split("\n\n") if b.strip()]
            if not raw_blocks:
                raw_blocks = [page_text]

            blocks = []
            for b in raw_blocks:
                # If block is a table, keep table as atomic block
                if b.startswith("|") and "|" in b:
                    blocks.append(b)
                elif len(b) > self.target_chunk_size * 1.5:
                    # Long paragraph: break into sentences
                    sents = self._split_into_sentences(b)
                    accum = ""
                    for s in sents:
                        if len(accum) + len(s) > self.target_chunk_size and accum:
                            blocks.append(accum.strip())
                            accum = s
                        else:
                            accum = (accum + " " + s).strip()
                    if accum:
                        blocks.append(accum.strip())
                else:
                    blocks.append(b)

            current_chunk_text = ""

            for block in blocks:
                # Detect sub-heading
                if len(block) < 80 and (
                    block.isupper()
                    or block.startswith("#")
                    or re.match(r"^\d+(\.\d+)*\s+[A-Z]", block)
                ):
                    subhead = block.lstrip("#").strip()
                    current_heading = subhead
                    if subhead not in current_breadcrumbs:
                        current_breadcrumbs.append(subhead)

                # Check if adding block exceeds target chunk size
                if len(current_chunk_text) + len(block) > self.target_chunk_size and current_chunk_text:
                    chunk_id = str(uuid.uuid4())
                    token_estimate = len(current_chunk_text.split())
                    has_table = "|" in current_chunk_text and "---" in current_chunk_text
                    
                    chunks.append(
                        DocumentChunkResult(
                            id=chunk_id,
                            workspace_id=workspace_id,
                            document_id=document_id,
                            chunk_index=global_chunk_idx,
                            page_number=page.page_number,
                            heading=current_heading,
                            text=current_chunk_text.strip(),
                            token_count=token_estimate,
                            metadata={
                                "document_title": document_title,
                                "source_filename": source_filename,
                                "page_number": page.page_number,
                                "heading": current_heading,
                                "section_breadcrumbs": current_breadcrumbs,
                                "has_table": has_table or getattr(page, "has_table", False),
                                "has_diagram": getattr(page, "has_diagram", False),
                                "figure_captions": getattr(page, "figure_captions", []),
                            },
                        )
                    )
                    global_chunk_idx += 1

                    # Retain overlap from end of previous text (skip overlap if previous block was a table)
                    if not has_table and len(current_chunk_text) > self.overlap_size:
                        overlap = current_chunk_text[-self.overlap_size :]
                    else:
                        overlap = ""
                    current_chunk_text = (overlap + "\n\n" + block).strip()
                else:
                    if current_chunk_text:
                        current_chunk_text += "\n\n" + block
                    else:
                        current_chunk_text = block

            # Remaining text for this page
            if current_chunk_text.strip():
                chunk_id = str(uuid.uuid4())
                token_estimate = len(current_chunk_text.split())
                has_table = "|" in current_chunk_text and "---" in current_chunk_text

                chunks.append(
                    DocumentChunkResult(
                        id=chunk_id,
                        workspace_id=workspace_id,
                        document_id=document_id,
                        chunk_index=global_chunk_idx,
                        page_number=page.page_number,
                        heading=current_heading,
                        text=current_chunk_text.strip(),
                        token_count=token_estimate,
                        metadata={
                            "document_title": document_title,
                            "source_filename": source_filename,
                            "page_number": page.page_number,
                            "heading": current_heading,
                            "section_breadcrumbs": current_breadcrumbs,
                            "has_table": has_table or getattr(page, "has_table", False),
                            "has_diagram": getattr(page, "has_diagram", False),
                            "figure_captions": getattr(page, "figure_captions", []),
                        },
                    )
                )
                global_chunk_idx += 1

        return chunks


chunker_service = SemanticChunkerService()

