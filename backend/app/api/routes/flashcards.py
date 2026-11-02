from datetime import date
from typing import List, Dict, Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.api.deps import require_workspace
from pydantic import BaseModel
from backend.app.repositories.secondary import flashcard_repo
from backend.app.services.secondary_service import secondary_service
from backend.app.services.spaced_repetition import schedule_review
from backend.app.repositories.secondary import activity_repo

router = APIRouter(tags=["Flashcards"], dependencies=[Depends(require_workspace)])


class FlashcardItem(BaseModel):
    id: str
    workspace_id: str
    front: str
    back: str
    concept: str
    source_document: str
    source_page: int
    interval_days: int = 1
    repetitions: int = 0
    ease_factor: float = 2.5
    review_count: int = 0
    last_rating: Optional[str] = None
    last_reviewed: Optional[date] = None
    due_date: Optional[date] = None


class FlashcardReviewRequest(BaseModel):
    rating: Literal["again", "hard", "good", "easy"]


class FlashcardListResponse(BaseModel):
    workspace_id: str
    total_count: int
    flashcards: List[FlashcardItem]
    # "preparing" while the concept-based deck is still being written in the background
    status: str = "ready"
    added_count: int = 0


def _deck_status(workspace_id: str) -> str:
    from backend.app.services.study_prep import study_prep_service

    return "preparing" if study_prep_service.is_running(workspace_id) else "ready"


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
        status=_deck_status(workspace_id),
    )


@router.post(
    "/workspaces/{workspace_id}/flashcards/generate",
    response_model=FlashcardListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_flashcards(workspace_id: str) -> FlashcardListResponse:
    """Adds new cards for the concepts the deck covers least (never repeating an existing card).

    Without an AI provider this returns the current (extractive) deck.
    """
    from backend.app.services.study_prep import ai_available, study_prep_service

    added: List[Dict[str, Any]] = []
    if ai_available():
        added = await study_prep_service.more_flashcards(workspace_id)
        cards = await flashcard_repo.list_by_workspace(workspace_id)
    else:
        cards = await secondary_service.get_or_generate_flashcards(workspace_id)
    return FlashcardListResponse(
        workspace_id=workspace_id,
        total_count=len(cards),
        flashcards=[FlashcardItem(**c) for c in cards],
        status=_deck_status(workspace_id),
        added_count=len(added),
    )


@router.get("/workspaces/{workspace_id}/study-material/status")
async def study_material_status(workspace_id: str) -> Dict[str, Any]:
    """Progress of the background preparation of topic map, flashcards and question bank."""
    from backend.app.services.study_prep import study_prep_service

    return {"workspace_id": workspace_id, **study_prep_service.status(workspace_id)}


@router.post(
    "/workspaces/{workspace_id}/flashcards/{card_id}/review",
    response_model=FlashcardItem,
)
async def review_flashcard(workspace_id: str, card_id: str, request: FlashcardReviewRequest) -> FlashcardItem:
    """Records a self-rated review and schedules the card's next due date with SM-2."""
    cards = await flashcard_repo.list_by_workspace(workspace_id)
    card = next((c for c in cards if c["id"] == card_id), None)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

    sched = schedule_review(
        request.rating,
        repetitions=int(card.get("repetitions") or 0),
        interval_days=int(card.get("interval_days") or 0),
        ease_factor=float(card.get("ease_factor") or 2.5),
    )
    updated = await flashcard_repo.record_review(
        workspace_id, card_id, request.rating, sched.repetitions, sched.interval_days, sched.ease_factor, sched.due_date
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

    if int(updated.get("review_count") or 0) == 1:
        try:
            await activity_repo.add_activity(
                workspace_id=workspace_id,
                event_type="flashcard_review",
                title=f"Flashcard reviewed: {updated.get('concept', 'concept')}",
                description=f"Rated '{request.rating}'; next review in {sched.interval_days} day(s).",
            )
        except Exception:
            pass
    return FlashcardItem(**updated)
