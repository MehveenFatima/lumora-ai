from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.api.deps import require_workspace
from backend.app.schemas.tutor import (
    TutorRequest,
    TutorResponse,
    ConversationHistoryResponse,
    MessagePayload,
)
from backend.app.services.tutor import tutor_service
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.tutor import tutor_repo
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["AI Tutor"], dependencies=[Depends(require_workspace)])


@router.post(
    "/workspaces/{workspace_id}/tutor",
    response_model=TutorResponse,
    status_code=status.HTTP_200_OK,
)
async def ask_tutor(
    workspace_id: str,
    request: TutorRequest,
) -> TutorResponse:
    """
    Asks the AI Tutor a question strictly grounded in the specified workspace's sources.
    Uses workspace-filtered pgvector search and Google Gemini for grounded generation.
    """
    # Verify workspace exists
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    try:
        response = await tutor_service.answer_question(
            workspace_id=workspace_id,
            user_message=request.message,
            conversation_id=request.conversation_id,
            current_document_id=request.current_document_id,
        )
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Tutor generation failed for workspace {workspace_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tutor service encountered an internal error: {str(e)}",
        )


@router.get(
    "/workspaces/{workspace_id}/tutor/history",
    response_model=ConversationHistoryResponse,
)
async def get_tutor_history(
    workspace_id: str,
    conversation_id: Optional[str] = None,
) -> ConversationHistoryResponse:
    workspace = await workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    resolved_conv_id = conversation_id
    if not resolved_conv_id:
        resolved_conv_id = await tutor_repo.get_latest_conversation_id(workspace_id)

    if not resolved_conv_id:
        return ConversationHistoryResponse(
            conversation_id="",
            workspace_id=workspace_id,
            messages=[],
            total_messages=0,
        )

    messages = await tutor_repo.get_recent_messages(resolved_conv_id, limit=50)
    return ConversationHistoryResponse(
        conversation_id=resolved_conv_id,
        workspace_id=workspace_id,
        messages=[
            MessagePayload(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                timestamp=str(m.get("created_at", "")),
            )
            for m in messages
        ],
        total_messages=len(messages),
    )
