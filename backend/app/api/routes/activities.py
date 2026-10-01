from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from backend.app.api.deps import CurrentUser, get_current_user, require_workspace
from backend.app.repositories.secondary import activity_repo
from backend.app.repositories.workspaces import workspace_repo

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
    dependencies=[Depends(require_workspace)],
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
    user: CurrentUser = Depends(get_current_user),
) -> ActivityListResponse:
    # Merge the most recent events across the workspaces this user owns
    acts = []
    for ws in await workspace_repo.list_by_owner(user["id"]):
        acts.extend(await activity_repo.list_by_workspace(ws["id"], limit=limit))
    acts.sort(key=lambda a: str(a.get("timestamp", "")), reverse=True)
    acts = acts[:limit]
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
    dependencies=[Depends(require_workspace)],
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
