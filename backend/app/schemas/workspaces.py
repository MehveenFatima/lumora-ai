from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class WorkspaceCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=300)
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    target_date: Optional[str] = "2026-12-31"
    daily_target_minutes: int = 45
    description: Optional[str] = ""
    icon_name: Optional[str] = "FolderKanban"


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    goal: str
    level: str
    target_date: Optional[str] = None
    daily_target_minutes: int
    description: Optional[str] = None
    overall_mastery: int = 0
    mastery_delta: int = 0
    status: str = "active"
    icon_name: str = "FolderKanban"
    document_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkspaceListResponse(BaseModel):
    workspaces: List[WorkspaceResponse]
    total_count: int
