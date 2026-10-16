from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.api.deps import CurrentUser, get_current_user
from backend.app.repositories.notifications import notification_repo
from backend.app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationItem(BaseModel):
    id: str
    type: str
    title: str
    message: str
    link: Optional[str] = None
    workspace_id: Optional[str] = None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    unread_count: int


def _to_item(n: dict) -> NotificationItem:
    return NotificationItem(
        id=n["id"], type=n["type"], title=n["title"], message=n["message"], link=n.get("link"),
        workspace_id=n.get("workspace_id"), read=n.get("read_at") is not None, created_at=n["created_at"],
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=50), user: CurrentUser = Depends(get_current_user)
) -> NotificationListResponse:
    # Time-based reminders (flashcards due today) are created when the list is opened
    await notification_service.refresh_due_flashcards(user["id"])
    items = await notification_repo.list_for_user(user["id"], limit=limit)
    return NotificationListResponse(
        items=[_to_item(n) for n in items], unread_count=await notification_repo.unread_count(user["id"])
    )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: CurrentUser = Depends(get_current_user)) -> None:
    await notification_repo.mark_all_read(user["id"])


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    if not await notification_repo.mark_read(user["id"], notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
