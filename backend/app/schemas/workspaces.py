from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from backend.app.core.dates import parse_date


def _check_target_date(v: Optional[str]) -> Optional[str]:
    if v is None or str(v).strip() == "":
        return None
    d = parse_date(v)
    if d is None:
        raise ValueError("Target completion date must be a valid date (YYYY-MM-DD).")
    return d.isoformat()


class WorkspaceCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=300)
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    # Must be today or later (checked against the learner's local date in the route)
    target_date: Optional[str] = None
    daily_target_minutes: int = Field(default=45, ge=5, le=600)
    description: Optional[str] = ""
    icon_name: Optional[str] = "FolderKanban"

    _target = field_validator("target_date")(classmethod(lambda cls, v: _check_target_date(v)))


class WorkspaceUpdateRequest(BaseModel):
    """Fields a learner can change after creating a workspace."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    goal: Optional[str] = Field(default=None, min_length=1, max_length=300)
    target_date: Optional[str] = None
    daily_target_minutes: Optional[int] = Field(default=None, ge=5, le=600)

    _target = field_validator("target_date")(classmethod(lambda cls, v: _check_target_date(v)))


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
