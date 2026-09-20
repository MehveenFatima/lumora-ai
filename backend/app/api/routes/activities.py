from typing import List, Optional
from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from backend.app.repositories.secondary import activity_repo

router = APIRouter(tags=["Activities"])


class ActivityItem(BaseModel):
    id: str
    workspace_id: str
    event_type: str
    title: str
    description: str
    timestamp: str


class ActivityListResponse(BaseModel):
    total_count: int
    activities: List[ActivityItem]


@router.get(
    "/workspaces/{workspace_id}/activity",
    response_model=ActivityListResponse,
)
async def get_workspace_activities(
    workspace_id: str,
    limit: int = Query(default=30, ge=1, le=100),
) -> ActivityListResponse:
    acts = await activity_repo.list_by_workspace(workspace_id, limit=limit)
    return ActivityListResponse(
        total_count=len(acts),
        activities=[ActivityItem(**a) for a in acts],
    )


@router.get(
    "/activities",
    response_model=ActivityListResponse,
)
async def get_all_activities(
    limit: int = Query(default=30, ge=1, le=100),
) -> ActivityListResponse:
    acts = await activity_repo.list_by_workspace(None, limit=limit)
    return ActivityListResponse(
        total_count=len(acts),
        activities=[ActivityItem(**a) for a in acts],
    )


class AddActivityRequest(BaseModel):
    event_type: str
    title: str
    description: str
    timestamp: Optional[str] = None


@router.post(
    "/workspaces/{workspace_id}/activity",
    response_model=ActivityItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity(
    workspace_id: str,
    request: AddActivityRequest,
) -> ActivityItem:
    item = await activity_repo.add_activity(
        workspace_id=workspace_id,
        event_type=request.event_type,
        title=request.title,
        description=request.description,
        timestamp=request.timestamp,
    )
    return ActivityItem(**item)
