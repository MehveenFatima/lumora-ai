from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from backend.app.schemas.quizzes import (
    QuizSessionCreateRequest,
    QuizSessionResponse,
    QuizQuestionPublicResponse,
    QuizQuestionAttemptRequest,
    QuizAttemptResultResponse,
    QuizSummaryResponse,
    QuizHistoryResponse,
    QuizNextBatchRequest,
    QuizNextBatchResponse,
)
from backend.app.services.quiz_service import quiz_service
from backend.app.services.question_generator import InsufficientContextError, NoIndexedDocumentsError
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Quizzes"])


@router.post(
    "/workspaces/{workspace_id}/quizzes",
    response_model=QuizSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_quiz_session(
    workspace_id: str,
    request: QuizSessionCreateRequest,
) -> QuizSessionResponse:
    try:
        session = await quiz_service.create_quiz_session(
            workspace_id=workspace_id,
            target_question_count=request.target_question_count,
            topic=request.topic,
            initial_difficulty=request.initial_difficulty,
        )
        return session
    except NoIndexedDocumentsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_INDEXED_DOCUMENTS", "message": str(e)},
        )
    except InsufficientContextError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create quiz session for workspace {workspace_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize adaptive quiz: {str(e)}",
        )


@router.get(
    "/workspaces/{workspace_id}/quizzes/history",
    response_model=QuizHistoryResponse,
)
async def get_quiz_history(
    workspace_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> QuizHistoryResponse:
    return await quiz_service.get_quiz_history(workspace_id, limit=limit, offset=offset)


@router.get(
    "/workspaces/{workspace_id}/quizzes/{quiz_id}",
    response_model=QuizSessionResponse,
)
async def get_quiz_session(
    workspace_id: str,
    quiz_id: str,
) -> QuizSessionResponse:
    session = await quiz_service.get_quiz_session(workspace_id, quiz_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session '{quiz_id}' not found in workspace '{workspace_id}'.",
        )
    return session


@router.get(
    "/workspaces/{workspace_id}/quizzes/{quiz_id}/questions/{question_id}",
    response_model=QuizQuestionPublicResponse,
)
async def get_quiz_question(
    workspace_id: str,
    quiz_id: str,
    question_id: str,
) -> QuizQuestionPublicResponse:
    question = await quiz_service.get_question(workspace_id, quiz_id, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_id}' not found in session '{quiz_id}'.",
        )
    return question


@router.post(
    "/workspaces/{workspace_id}/quizzes/{quiz_id}/questions/{question_id}/attempt",
    response_model=QuizAttemptResultResponse,
)
async def submit_quiz_attempt(
    workspace_id: str,
    quiz_id: str,
    question_id: str,
    request: QuizQuestionAttemptRequest,
) -> QuizAttemptResultResponse:
    try:
        result = await quiz_service.submit_attempt(
            workspace_id=workspace_id,
            session_id=quiz_id,
            question_id=question_id,
            selected_option=request.selected_option,
            response_time_ms=request.response_time_ms,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to submit attempt for question {question_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process quiz attempt: {str(e)}",
        )


@router.post(
    "/workspaces/{workspace_id}/quizzes/{quiz_id}/complete",
    response_model=QuizSummaryResponse,
)
async def complete_quiz_session(
    workspace_id: str,
    quiz_id: str,
) -> QuizSummaryResponse:
    try:
        summary = await quiz_service.complete_quiz(workspace_id, quiz_id)
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to complete quiz {quiz_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize quiz summary: {str(e)}",
        )


@router.post(
    "/workspaces/{workspace_id}/quizzes/{quiz_id}/next-batch",
    response_model=QuizNextBatchResponse,
)
async def start_next_quiz_batch(
    workspace_id: str,
    quiz_id: str,
    request: Optional[QuizNextBatchRequest] = None,
) -> QuizNextBatchResponse:
    batch_size = request.batch_size if request else 5
    try:
        response = await quiz_service.start_next_batch(
            workspace_id=workspace_id,
            session_id=quiz_id,
            batch_size=batch_size,
        )
        return response
    except NoIndexedDocumentsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_INDEXED_DOCUMENTS", "message": str(e)},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to start next batch for quiz {quiz_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate next adaptive batch: {str(e)}",
        )

