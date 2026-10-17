"""
Authentication and authorization dependencies shared by all routers.

- `get_current_user` resolves the signed-in user from the session cookie or a Bearer token.
- `require_workspace` loads a workspace from the `workspace_id` path parameter and checks that
  the current user owns it. Workspaces belonging to someone else return 404, so the API never
  reveals whether another user's workspace exists.
"""
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from backend.app.core.config import settings
from backend.app.core.security import decode_session_claims, password_version
from backend.app.repositories.users import user_repo
from backend.app.repositories.workspaces import workspace_repo

CurrentUser = Dict[str, Any]


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    return request.cookies.get(settings.session_cookie_name)


def _session_still_valid(user: Dict[str, Any], claims: Dict[str, Any]) -> bool:
    """A password change (or reset) ends every session that was issued before it."""
    return int(claims.get("pv", 0) or 0) == password_version(user.get("password_changed_at"))


async def get_current_user(request: Request) -> CurrentUser:
    token = _extract_token(request)
    claims = decode_session_claims(token) if token else None
    user = await user_repo.get_by_id(str(claims["sub"])) if claims else None
    if user and (not _session_still_valid(user, claims) or user.get("email_verified") is False):
        user = None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_workspace(workspace_id: str, user: CurrentUser = Depends(get_current_user)) -> Dict[str, Any]:
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace or workspace.get("owner_id") != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )
    return workspace


async def ensure_document_access(document: Optional[Dict[str, Any]], user: CurrentUser) -> Dict[str, Any]:
    """Raises 404 unless the document exists and belongs to a workspace the user owns."""
    if document:
        workspace = await workspace_repo.get_by_id(str(document.get("workspace_id")))
        if workspace and workspace.get("owner_id") == user["id"]:
            return document
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")


def internal_error_detail(message: str, exc: Exception) -> str:
    """Client-facing text for an unexpected 500: includes the exception only outside production."""
    return message if settings.is_production else f"{message}: {exc}"
