"""
LumoraAI - Mastery and Learner Profile Schemas
Pydantic v2 schemas for Concept, Topic, and Workspace Learner Profile telemetry.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ConceptMasteryDetail(BaseModel):
    concept: str
    topic: str
    p_mastery: float = 0.30
    mastery_percentage: int = 30
    confidence_level: str = "low"  # 'low', 'moderate', 'high'
    mastery_status: str = "developing"  # 'strong', 'developing', 'needs_review', 'critical_gap', 'low_evidence'
    trend: str = "insufficient_data"  # 'improving', 'declining', 'stable', 'insufficient_data'
    attempts_count: int = 0
    correct_count: int = 0
    recent_accuracy: float = 0.0
    average_response_time_ms: int = 0
    last_practiced_at: Optional[datetime] = None


class TopicMasteryDetail(BaseModel):
    topic: str
    workspace_id: str
    mastery_probability: float = 0.30
    mastery_percentage: int = 30
    confidence_level: str = "low"
    mastery_status: str = "developing"
    trend: str = "insufficient_data"
    concept_count: int = 0
    assessed_concept_count: int = 0
    coverage_ratio: float = 0.0
    attempt_count: int = 0
    correct_count: int = 0
    recent_accuracy: float = 0.0
    average_response_time_ms: int = 0
    gap_priority: float = 0.0
    concepts: Optional[List[ConceptMasteryDetail]] = None
    last_assessed_at: Optional[datetime] = None


class TopicMasteryListResponse(BaseModel):
    workspace_id: str
    topics: List[TopicMasteryDetail]
    total_count: int


class RecommendationItem(BaseModel):
    workspace_id: str
    topic: str
    concept: str
    mastery_probability: float
    gap_priority: float
    confidence: str
    trend: str
    recent_accuracy: float
    repeated_errors: int
    recommended_action: str


class OverallMasterySummary(BaseModel):
    mastery_percentage: int = 0
    mastery_probability: float = 0.0
    mastery_delta: int = 0
    status: str = "not_assessed"
    confidence: str = "none"
    coverage_ratio: float = 0.0
    assessed_concepts_count: int = 0
    total_concepts_count: int = 0
    assessed_topics_count: int = 0
    total_topics_count: int = 0


class RecentPerformanceSummary(BaseModel):
    quizzes_completed: int = 0
    total_attempts: int = 0
    accuracy_percentage: int = 0
    average_response_time_seconds: float = 0.0


class LearnerProfileResponse(BaseModel):
    workspace_id: str
    status: str  # 'assessed', 'not_assessed'
    message: Optional[str] = None
    overall: OverallMasterySummary
    strongest_topics: List[TopicMasteryDetail] = []
    weakest_topics: List[TopicMasteryDetail] = []
    top_knowledge_gaps: List[Dict[str, Any]] = []
    improving_topics: List[TopicMasteryDetail] = []
    declining_topics: List[TopicMasteryDetail] = []
    recent_performance: RecentPerformanceSummary
    recommendations: List[RecommendationItem] = []
    last_updated: str


class WorkspaceMasteryOverviewResponse(BaseModel):
    workspace_id: str
    overall: OverallMasterySummary
    topics: List[TopicMasteryDetail] = []
    concepts: List[ConceptMasteryDetail] = []
    knowledge_gaps: List[Dict[str, Any]] = []
