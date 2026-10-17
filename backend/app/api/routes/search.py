from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.api.deps import require_workspace
from backend.app.services.search_service import search_service

router = APIRouter(tags=["Search"], dependencies=[Depends(require_workspace)])


class SearchResult(BaseModel):
    type: str
    title: str
    snippet: str = ""
    link: str
    meta: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]


@router.get("/workspaces/{workspace_id}/search", response_model=SearchResponse)
async def search_workspace(workspace_id: str, q: str = Query(default="", max_length=100)) -> SearchResponse:
    return SearchResponse(**await search_service.search(workspace_id, q))
