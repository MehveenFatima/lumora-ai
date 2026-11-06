from typing import Optional, List, Literal
from pydantic import BaseModel, model_validator, Field
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
    # A failed file whose original is still stored can be processed again
    can_retry: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _retry_flag(cls, data):
        if isinstance(data, dict) and "can_retry" not in data:
            data = {**data, "can_retry": data.get("status") == "failed" and bool(data.get("storage_path"))}
        return data


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
