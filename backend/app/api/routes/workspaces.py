import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from backend.app.schemas.workspaces import (
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceListResponse,
)
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Workspaces"])


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(request: WorkspaceCreateRequest) -> WorkspaceResponse:
    ws_id = request.id or f"ws_{int(uuid.uuid4().hex[:12], 16)}"
    created = await workspace_repo.create(
        workspace_id=ws_id,
        name=request.name,
        goal=request.goal,
        level=request.level,
        target_date=request.target_date,
        daily_target_minutes=request.daily_target_minutes,
        description=request.description or "",
        icon_name=request.icon_name or "FolderKanban",
    )
    return WorkspaceResponse(
        id=created["id"],
        name=created["name"],
        goal=created["goal"],
        level=created["level"],
        target_date=str(created.get("target_date", "2026-12-31")),
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


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces() -> WorkspaceListResponse:
    workspaces = await workspace_repo.list_all()
    return WorkspaceListResponse(
        workspaces=[
            WorkspaceResponse(
                id=w["id"],
                name=w["name"],
                goal=w["goal"],
                level=w.get("level", "intermediate"),
                target_date=str(w.get("target_date", "2026-12-31")),
                daily_target_minutes=w.get("daily_target_minutes", 45),
                description=w.get("description", ""),
                overall_mastery=w.get("overall_mastery", 0),
                mastery_delta=w.get("mastery_delta", 0),
                status=w.get("status", "active"),
                icon_name=w.get("icon_name", "FolderKanban"),
                document_count=w.get("document_count", 0),
                created_at=w.get("created_at"),
                updated_at=w.get("updated_at"),
            )
            for w in workspaces
        ],
        total_count=len(workspaces),
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    ws = await workspace_repo.get_by_id(workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )
    return WorkspaceResponse(
        id=ws["id"],
        name=ws["name"],
        goal=ws["goal"],
        level=ws.get("level", "intermediate"),
        target_date=str(ws.get("target_date", "2026-12-31")),
        daily_target_minutes=ws.get("daily_target_minutes", 45),
        description=ws.get("description", ""),
        overall_mastery=ws.get("overall_mastery", 0),
        mastery_delta=ws.get("mastery_delta", 0),
        status=ws.get("status", "active"),
        icon_name=ws.get("icon_name", "FolderKanban"),
        document_count=ws.get("document_count", 0),
        created_at=ws.get("created_at"),
        updated_at=ws.get("updated_at"),
    )


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_200_OK)
async def delete_workspace(workspace_id: str):
    ws = await workspace_repo.get_by_id(workspace_id)
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

    await workspace_repo.delete(workspace_id)
    return {"success": True, "message": f"Workspace '{workspace_id}' and all associated documents deleted."}
