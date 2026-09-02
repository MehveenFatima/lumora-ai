from typing import List, Dict, Any, Optional
import uuid
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

    def chunk_pages(
        self,
        workspace_id: str,
        document_id: str,
        pages: List[ParsedPage],
        document_title: str = "",
    ) -> List[DocumentChunkResult]:
        chunks: List[DocumentChunkResult] = []
        global_chunk_idx = 0

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            # Split page text into paragraphs/sections
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [page_text]

            current_chunk_text = ""
            current_heading = page.heading

            for para in paragraphs:
                # If paragraph looks like a heading (short line, uppercase or starts with #)
                if len(para) < 70 and (para.isupper() or para.startswith("#")):
                    current_heading = para.lstrip("#").strip()

                if len(current_chunk_text) + len(para) > self.target_chunk_size and current_chunk_text:
                    # Finalize current chunk
                    chunk_id = str(uuid.uuid4())
                    token_estimate = len(current_chunk_text.split())
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
                                "page_number": page.page_number,
                                "heading": current_heading,
                            },
                        )
                    )
                    global_chunk_idx += 1

                    # Retain overlap from end of previous text
                    overlap = current_chunk_text[-self.overlap_size :] if len(current_chunk_text) > self.overlap_size else ""
                    current_chunk_text = overlap + "\n" + para
                else:
                    if current_chunk_text:
                        current_chunk_text += "\n\n" + para
                    else:
                        current_chunk_text = para

            # Remaining text in page
            if current_chunk_text.strip():
                chunk_id = str(uuid.uuid4())
                token_estimate = len(current_chunk_text.split())
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
                            "page_number": page.page_number,
                            "heading": current_heading,
                        },
                    )
                )
                global_chunk_idx += 1

        return chunks


chunker_service = SemanticChunkerService()
