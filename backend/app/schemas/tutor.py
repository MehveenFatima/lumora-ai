from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TutorCitationSchema(BaseModel):
    id: str
    document_id: str
    document_name: str
    page_or_slide: int
    excerpt: str
    relevance_score: float


class MessagePayload(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[str] = None


class RetrievalMetadata(BaseModel):
    chunks_considered: int
    grounded: bool
    top_similarity_score: Optional[float] = None
    query_terms: Optional[List[str]] = None


class TutorRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    current_document_id: Optional[str] = None


class TutorResponse(BaseModel):
    conversation_id: str
    message: MessagePayload
    citations: List[TutorCitationSchema] = Field(default_factory=list)
    retrieval: RetrievalMetadata
    suggested_follow_ups: List[str] = Field(default_factory=list)


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    workspace_id: str
    messages: List[MessagePayload]
    total_messages: int
