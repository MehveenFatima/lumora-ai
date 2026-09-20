from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from backend.app.repositories.secondary import flashcard_repo
from backend.app.services.secondary_service import secondary_service

router = APIRouter(tags=["Flashcards"])


class FlashcardItem(BaseModel):
    id: str
    workspace_id: str
    front: str
    back: str
    concept: str
    source_document: str
    source_page: int
    interval_days: int = 1


class FlashcardListResponse(BaseModel):
    workspace_id: str
    total_count: int
    flashcards: List[FlashcardItem]


@router.get(
    "/workspaces/{workspace_id}/flashcards",
    response_model=FlashcardListResponse,
)
async def get_flashcards(workspace_id: str) -> FlashcardListResponse:
    cards = await secondary_service.get_or_generate_flashcards(workspace_id)
    return FlashcardListResponse(
        workspace_id=workspace_id,
        total_count=len(cards),
        flashcards=[FlashcardItem(**c) for c in cards],
    )


@router.post(
    "/workspaces/{workspace_id}/flashcards/generate",
    response_model=FlashcardListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_flashcards(workspace_id: str) -> FlashcardListResponse:
    cards = await secondary_service.get_or_generate_flashcards(workspace_id)
    return FlashcardListResponse(
        workspace_id=workspace_id,
        total_count=len(cards),
        flashcards=[FlashcardItem(**c) for c in cards],
    )
