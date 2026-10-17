import uuid
from typing import List
from backend.app.services.storage import storage_service
from fastapi import APIRouter, Depends, HTTPException, Request, status
from backend.app.core.dates import client_today, format_long, parse_date
from backend.app.api.deps import CurrentUser, get_current_user, require_workspace
from backend.app.schemas.workspaces import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    WorkspaceResponse,
    WorkspaceListResponse,
)
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Workspaces"])


def _reject_past_target(target_date, http_request: Request) -> None:
    """A target completion date may be today or any later day, never in the past."""
    target = parse_date(target_date)
    today = client_today(http_request)
    if target and target < today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Target completion date can't be in the past. Choose today ({format_long(today)}) or a later date.",
        )


def _iso(value):
    d = parse_date(value)
    return d.isoformat() if d else None


def _to_response(ws: dict, document_count=None) -> WorkspaceResponse:
    target = parse_date(ws.get("target_date"))
    return WorkspaceResponse(
        id=ws["id"],
        name=ws["name"],
        goal=ws["goal"],
        level=ws.get("level", "intermediate"),
        target_date=target.isoformat() if target else None,
        daily_target_minutes=ws.get("daily_target_minutes", 45),
        description=ws.get("description", ""),
        overall_mastery=ws.get("overall_mastery", 0),
        mastery_delta=ws.get("mastery_delta", 0),
        status=ws.get("status", "active"),
        icon_name=ws.get("icon_name", "FolderKanban"),
        document_count=ws.get("document_count", 0) if document_count is None else document_count,
        created_at=ws.get("created_at"),
        updated_at=ws.get("updated_at"),
    )


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    request: WorkspaceCreateRequest, http_request: Request, user: CurrentUser = Depends(get_current_user)
) -> WorkspaceResponse:
    _reject_past_target(request.target_date, http_request)
    try:
        # IDs are always generated server-side so a client cannot target an existing workspace
        ws_id = f"ws_{uuid.uuid4().hex[:16]}"
        created = await workspace_repo.create(
            workspace_id=ws_id,
            name=request.name,
            goal=request.goal,
            level=request.level,
            target_date=request.target_date or None,
            daily_target_minutes=request.daily_target_minutes,
            description=request.description or "",
            icon_name=request.icon_name or "FolderKanban",
            owner_id=user["id"],
        )
        return WorkspaceResponse(
            id=created["id"],
            name=created["name"],
            goal=created["goal"],
            level=created["level"],
            target_date=_iso(created.get("target_date")),
            daily_target_minutes=created.get("daily_target_minutes", 45),
            description=created.get("description", ""),
            overall_mastery=created.get("overall_mastery", 0),
            mastery_delta=created.get("mastery_delta", 0),
            status=created.get("status", "active"),
            icon_name=created.get("icon_name", "FolderKanban"),
            document_count=created.get("document_count", 0),
            created_at=created.get("created_at"),
            updated_at=created.get("updated_at"),
        )
    except Exception as e:
        logger.error(f"Failed to create workspace '{request.name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace.",
        )


from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query

@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces(
    name: Optional[str] = Query(default=None), user: CurrentUser = Depends(get_current_user)
) -> WorkspaceListResponse:
    workspaces = await workspace_repo.list_by_owner(user["id"])
    if name:
        target = name.strip().lower()
        workspaces = [w for w in workspaces if (w.get("name") or "").strip().lower() == target]
    responses = []
    for w in workspaces:
        docs = await document_repo.list_by_workspace(w["id"])
        doc_count = len(docs) if docs is not None else w.get("document_count", 0)
        responses.append(
            WorkspaceResponse(
                id=w["id"],
                name=w["name"],
                goal=w["goal"],
                level=w.get("level", "intermediate"),
                target_date=_iso(w.get("target_date")),
                daily_target_minutes=w.get("daily_target_minutes", 45),
                description=w.get("description", ""),
                overall_mastery=w.get("overall_mastery", 0),
                mastery_delta=w.get("mastery_delta", 0),
                status=w.get("status", "active"),
                icon_name=w.get("icon_name", "FolderKanban"),
                document_count=doc_count,
                created_at=w.get("created_at"),
                updated_at=w.get("updated_at"),
            )
        )
    return WorkspaceListResponse(
        workspaces=responses,
        total_count=len(responses),
    )


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdateRequest,
    http_request: Request,
    ws: dict = Depends(require_workspace),
) -> WorkspaceResponse:
    """Updates the workspace's name, goal, target completion date or daily study target."""
    _reject_past_target(payload.target_date, http_request)
    updated = await workspace_repo.update_settings(workspace_id, payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workspace '{workspace_id}' not found.")
    docs = await document_repo.list_by_workspace(workspace_id)
    return _to_response(updated, len(docs))


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, ws: dict = Depends(require_workspace)) -> WorkspaceResponse:
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )
    docs = await document_repo.list_by_workspace(workspace_id)
    doc_count = len(docs) if docs is not None else ws.get("document_count", 0)

    return WorkspaceResponse(
        id=ws["id"],
        name=ws["name"],
        goal=ws["goal"],
        level=ws.get("level", "intermediate"),
        target_date=_iso(ws.get("target_date")),
        daily_target_minutes=ws.get("daily_target_minutes", 45),
        description=ws.get("description", ""),
        overall_mastery=ws.get("overall_mastery", 0),
        mastery_delta=ws.get("mastery_delta", 0),
        status=ws.get("status", "active"),
        icon_name=ws.get("icon_name", "FolderKanban"),
        document_count=doc_count,
        created_at=ws.get("created_at"),
        updated_at=ws.get("updated_at"),
    )


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_200_OK)
async def delete_workspace(workspace_id: str, ws: dict = Depends(require_workspace)):
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    # Delete all documents for workspace
    docs = await document_repo.list_by_workspace(workspace_id)
    for doc in docs:
        await chunk_repo.delete_by_document(doc["id"])
        await document_repo.delete(doc["id"])
        await storage_service.delete_file(doc.get("storage_path"))

    await workspace_repo.delete(workspace_id)
    return {"success": True, "message": f"Workspace '{workspace_id}' and all associated documents deleted."}
