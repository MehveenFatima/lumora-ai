from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


DocumentType = Literal["pdf", "docx", "pptx", "txt"]
DocumentStatus = Literal[
    "uploading", "processing", "extracting", "indexing", "ready", "failed"
]


class DocumentChunkSchema(BaseModel):
    id: str
    chunk_index: int
    page_number: int
    heading: Optional[str] = None
    text: str
    token_count: Optional[int] = None
    relevance_score: Optional[float] = None


class DocumentResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    filename: str
    file_type: DocumentType
    file_size: int
    page_count: int
    status: DocumentStatus
    chunk_count: int
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    filename: str
    file_type: DocumentType
    file_size: int
    page_count: int
    status: DocumentStatus
    message: str = "Document uploaded and queued for processing"


class DocumentListResponse(BaseModel):
    workspace_id: str
    documents: List[DocumentResponse]
    total_count: int
