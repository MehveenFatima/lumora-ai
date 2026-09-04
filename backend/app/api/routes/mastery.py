"""
LumoraAI - Topic Mastery and Learner Profile API Routes
Authoritative endpoints for workspace-scoped topic mastery, concept hierarchies,
and the Learner Knowledge Profile.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query

from backend.app.core.logging import get_logger
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.services.topic_mastery_engine import (
    topic_mastery_engine,
    normalize_topic_name,
)
from backend.app.services.learner_profile_service import learner_profile_service
from backend.app.schemas.mastery import (
    ConceptMasteryDetail,
    TopicMasteryDetail,
    TopicMasteryListResponse,
    LearnerProfileResponse,
    WorkspaceMasteryOverviewResponse,
    OverallMasterySummary,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Topic Mastery & Profile"])


@router.get(
    "/learner-profile",
    response_model=LearnerProfileResponse,
    summary="Get Workspace Learner Knowledge Profile",
)
async def get_workspace_learner_profile(
    workspace_id: str,
    user_id: str = Query(default="default_user"),
) -> LearnerProfileResponse:
    ws = await workspace_repo.get_by_id(workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    profile_data = await learner_profile_service.get_learner_profile(workspace_id, user_id)
    return LearnerProfileResponse(**profile_data)


@router.get(
    "/mastery",
    response_model=WorkspaceMasteryOverviewResponse,
    summary="Get Workspace Mastery Overview",
)
async def get_workspace_mastery_overview(
    workspace_id: str,
    user_id: str = Query(default="default_user"),
) -> WorkspaceMasteryOverviewResponse:
    ws = await workspace_repo.get_by_id(workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    profile_data = await learner_profile_service.get_learner_profile(workspace_id, user_id)
    raw_topics = await topic_mastery_repo.list_topic_mastery(workspace_id, user_id)
    raw_concepts = await bkt_repo.list_concept_mastery(workspace_id, user_id)
    raw_gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)

    topics_res = [
        TopicMasteryDetail(
            topic=t.get("topic"),
            workspace_id=workspace_id,
            mastery_probability=t.get("mastery_probability", 0.30),
            mastery_percentage=int(round(t.get("mastery_probability", 0.30) * 100)),
            confidence_level=t.get("confidence_level", "low"),
            mastery_status=t.get("mastery_status", "developing"),
            trend=t.get("trend", "insufficient_data"),
            concept_count=t.get("concept_count", 0),
            assessed_concept_count=t.get("assessed_concept_count", 0),
            coverage_ratio=t.get("coverage_ratio", 0.0),
            attempt_count=t.get("attempt_count", 0),
            correct_count=t.get("correct_count", 0),
            recent_accuracy=t.get("recent_accuracy", 0.0),
            average_response_time_ms=t.get("average_response_time_ms", 0),
            gap_priority=t.get("gap_priority", 0.0),
            last_assessed_at=t.get("last_assessed_at"),
        )
        for t in raw_topics
    ]

    concepts_res = [
        ConceptMasteryDetail(
            concept=c.get("concept"),
            topic=c.get("topic"),
            p_mastery=c.get("p_mastery", 0.30),
            mastery_percentage=int(round(c.get("p_mastery", 0.30) * 100)),
            confidence_level=c.get("confidence_level", "low"),
            mastery_status=c.get("mastery_status", "developing"),
            trend=c.get("trend", "insufficient_data"),
            attempts_count=c.get("attempts_count", 0),
            correct_count=c.get("correct_count", 0),
            recent_accuracy=c.get("recent_accuracy", 0.0),
            average_response_time_ms=c.get("average_response_time_ms", 0),
            last_practiced_at=c.get("last_practiced_at"),
        )
        for c in raw_concepts
    ]

    return WorkspaceMasteryOverviewResponse(
        workspace_id=workspace_id,
        overall=OverallMasterySummary(**profile_data["overall"]),
        topics=topics_res,
        concepts=concepts_res,
        knowledge_gaps=raw_gaps,
    )


@router.get(
    "/mastery/topics",
    response_model=TopicMasteryListResponse,
    summary="List Workspace Topics Mastery",
)
async def list_workspace_topics(
    workspace_id: str,
    user_id: str = Query(default="default_user"),
) -> TopicMasteryListResponse:
    ws = await workspace_repo.get_by_id(workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    raw_topics = await topic_mastery_repo.list_topic_mastery(workspace_id, user_id)
    if not raw_topics:
        raw_topics = await topic_mastery_engine.recalculate_all_workspace_topics(workspace_id, user_id)

    topics_res = [
        TopicMasteryDetail(
            topic=t.get("topic"),
            workspace_id=workspace_id,
            mastery_probability=t.get("mastery_probability", 0.30),
            mastery_percentage=int(round(t.get("mastery_probability", 0.30) * 100)),
            confidence_level=t.get("confidence_level", "low"),
            mastery_status=t.get("mastery_status", "developing"),
            trend=t.get("trend", "insufficient_data"),
            concept_count=t.get("concept_count", 0),
            assessed_concept_count=t.get("assessed_concept_count", 0),
            coverage_ratio=t.get("coverage_ratio", 0.0),
            attempt_count=t.get("attempt_count", 0),
            correct_count=t.get("correct_count", 0),
            recent_accuracy=t.get("recent_accuracy", 0.0),
            average_response_time_ms=t.get("average_response_time_ms", 0),
            gap_priority=t.get("gap_priority", 0.0),
            last_assessed_at=t.get("last_assessed_at"),
        )
        for t in raw_topics
    ]

    return TopicMasteryListResponse(
        workspace_id=workspace_id,
        topics=topics_res,
        total_count=len(topics_res),
    )


@router.get(
    "/mastery/topics/{topic}",
    response_model=TopicMasteryDetail,
    summary="Get Topic Mastery Detail with Underlying Concepts",
)
async def get_topic_detail(
    workspace_id: str,
    topic: str,
    user_id: str = Query(default="default_user"),
) -> TopicMasteryDetail:
    ws = await workspace_repo.get_by_id(workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )

    norm_topic = normalize_topic_name(topic)
    topic_record = await topic_mastery_repo.get_topic_mastery(workspace_id, norm_topic, user_id)
    if not topic_record:
        topic_record = await topic_mastery_engine.recalculate_topic(workspace_id, norm_topic, user_id=user_id)

    all_concepts = await bkt_repo.list_concept_mastery(workspace_id, user_id)
    matching_concepts = [
        ConceptMasteryDetail(
            concept=c.get("concept"),
            topic=c.get("topic"),
            p_mastery=c.get("p_mastery", 0.30),
            mastery_percentage=int(round(c.get("p_mastery", 0.30) * 100)),
            confidence_level=c.get("confidence_level", "low"),
            mastery_status=c.get("mastery_status", "developing"),
            trend=c.get("trend", "insufficient_data"),
            attempts_count=c.get("attempts_count", 0),
            correct_count=c.get("correct_count", 0),
            recent_accuracy=c.get("recent_accuracy", 0.0),
            average_response_time_ms=c.get("average_response_time_ms", 0),
            last_practiced_at=c.get("last_practiced_at"),
        )
        for c in all_concepts
        if normalize_topic_name(c.get("topic", "")) == norm_topic
    ]

    return TopicMasteryDetail(
        topic=norm_topic,
        workspace_id=workspace_id,
        mastery_probability=topic_record.get("mastery_probability", 0.30),
        mastery_percentage=int(round(topic_record.get("mastery_probability", 0.30) * 100)),
        confidence_level=topic_record.get("confidence_level", "low"),
        mastery_status=topic_record.get("mastery_status", "developing"),
        trend=topic_record.get("trend", "insufficient_data"),
        concept_count=max(topic_record.get("concept_count", len(matching_concepts)), len(matching_concepts), 1),
        assessed_concept_count=len(matching_concepts),
        coverage_ratio=topic_record.get("coverage_ratio", 0.0),
        attempt_count=topic_record.get("attempt_count", 0),
        correct_count=topic_record.get("correct_count", 0),
        recent_accuracy=topic_record.get("recent_accuracy", 0.0),
        average_response_time_ms=topic_record.get("average_response_time_ms", 0),
        gap_priority=topic_record.get("gap_priority", 0.0),
        concepts=matching_concepts,
        last_assessed_at=topic_record.get("last_assessed_at"),
    )
