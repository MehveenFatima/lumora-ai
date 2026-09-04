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
    status: str  # 'strong', 'developing', 'needs_review'


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


class QuizSummaryResponse(BaseModel):
    session_id: str
    workspace_id: str
    status: str
    total_questions: int
    correct_count: int
    score: int
    accuracy_percentage: int
    average_response_time_seconds: float
    topics_breakdown: List[TopicPerformanceSummary]
    difficulty_breakdown: List[DifficultyPerformanceSummary]
    concept_performance: List[ConceptPerformanceSchema]
    knowledge_gaps_identified: List[str]
    recommendation: str
    completed_at: Optional[datetime] = None


class QuizHistoryItemResponse(BaseModel):
    id: str
    workspace_id: str
    status: str
    total_questions: int
    correct_count: int
    score: int
    accuracy_percentage: int
    average_response_time_seconds: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class QuizHistoryResponse(BaseModel):
    sessions: List[QuizHistoryItemResponse]
    total_count: int
