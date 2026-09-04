from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class QuizOptionSchema(BaseModel):
    key: str = Field(..., description="Option key, e.g. 'A', 'B', 'C', 'D'")
    text: str = Field(..., description="Option text content")


class QuizQuestionPublicResponse(BaseModel):
    id: str
    quiz_session_id: str
    workspace_id: str
    question_index: int
    topic: str
    concept: str
    difficulty: int = Field(..., description="1 = Easy, 2 = Medium, 3 = Hard")
    difficulty_label: str = Field(..., description="'easy', 'medium', 'hard'")
    question_text: str
    options: List[QuizOptionSchema]
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    fingerprint: Optional[str] = None
    created_at: Optional[datetime] = None


class QuizSessionCreateRequest(BaseModel):
    target_question_count: int = Field(default=5, ge=1, le=20)
    topic: Optional[str] = Field(default=None, description="Optional topic focus")
    initial_difficulty: int = Field(default=2, ge=1, le=3, description="1=Easy, 2=Medium, 3=Hard")


class QuizSessionResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    status: str
    target_question_count: int
    current_question_index: int
    score: int
    correct_count: int
    total_count: int
    average_response_time_ms: int
    adaptation_round: int = 1
    initial_diagnostic_completed: bool = False
    current_adaptation_stage: str = "diagnostic"
    current_question: Optional[QuizQuestionPublicResponse] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class QuizQuestionAttemptRequest(BaseModel):
    selected_option: str = Field(..., description="'A', 'B', 'C', or 'D'")
    response_time_ms: int = Field(default=0, ge=0)


class ConceptPerformanceSchema(BaseModel):
    concept_name: str
    topic_name: str
    attempts: int
    correct: int
    accuracy_percentage: int
    p_mastery: Optional[float] = 0.30
    mastery_percentage: Optional[int] = 30
    gap_priority: Optional[float] = 0.50
    status: str  # 'strong', 'developing', 'needs_attention', 'critical_gap'
    recommended_action: Optional[str] = "targeted_practice"


class QuizAttemptResultResponse(BaseModel):
    attempt_id: str
    question_id: str
    selected_option: str
    is_correct: bool
    correct_option: str
    explanation: str
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    source_excerpt: Optional[str] = None
    response_time_ms: int
    current_score: int
    current_question_index: int
    target_question_count: int
    is_quiz_completed: bool
    adaptation_round: int = 1
    next_question: Optional[QuizQuestionPublicResponse] = None
    adaptation_metadata: Optional[Dict[str, Any]] = None


class TopicPerformanceSummary(BaseModel):
    topic: str
    total_questions: int
    correct: int
    accuracy_percentage: int
    mastery_status: str


class DifficultyPerformanceSummary(BaseModel):
    difficulty: int
    difficulty_label: str
    total_questions: int
    correct: int
    accuracy_percentage: int


class KnowledgeGapDetail(BaseModel):
    concept: str
    topic: str
    gap_priority: float
    status: str
    p_mastery: float
    recommended_action: str


class QuizSummaryResponse(BaseModel):
    session_id: str
    workspace_id: str
    status: str
    target_question_count: int
    total_questions: int
    correct_count: int
    score: int
    accuracy_percentage: int
    average_response_time_seconds: float
    adaptation_round: int = 1
    topics_breakdown: List[TopicPerformanceSummary]
    difficulty_breakdown: List[DifficultyPerformanceSummary]
    concept_performance: List[ConceptPerformanceSchema]
    knowledge_gaps: List[KnowledgeGapDetail] = []
    knowledge_gaps_identified: List[str] = []
    recommendation: str
    completed_at: Optional[datetime] = None


class QuizNextBatchRequest(BaseModel):
    batch_size: int = Field(default=5, ge=1, le=10)


class QuizNextBatchResponse(BaseModel):
    session_id: str
    workspace_id: str
    adaptation_round: int
    current_adaptation_stage: str
    target_concepts: List[str]
    new_questions_count: int
    first_question: QuizQuestionPublicResponse


class QuizHistoryItemResponse(BaseModel):
    id: str
    workspace_id: str
    status: str
    target_question_count: int
    total_questions: int
    correct_count: int
    score: int
    accuracy_percentage: int
    average_response_time_seconds: float
    adaptation_round: int = 1
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class QuizHistoryResponse(BaseModel):
    sessions: List[QuizHistoryItemResponse]
    total_count: int
