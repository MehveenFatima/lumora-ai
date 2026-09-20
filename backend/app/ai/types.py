from enum import Enum
from typing import Optional, List, Dict, Any, Union, Type
from pydantic import BaseModel, Field, ConfigDict


class TaskType(str, Enum):
    TUTOR = "tutor"
    QUIZ = "quiz"
    FLASHCARDS = "flashcards"
    GENERAL = "general"


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    COOLDOWN = "cooldown"
    UNCONFIGURED = "unconfigured"
    ERROR = "error"


# -------------------------------------------------------------
# Gateway Exceptions (Categorized for Failover & Observability)
# -------------------------------------------------------------
class AIGatewayError(Exception):
    """Base exception for all AI Gateway errors."""
    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message)
        self.provider = provider
        self.message = message


class RateLimitError(AIGatewayError):
    """Raised when an AI provider returns HTTP 429 or quota exceeded."""
    pass


class AITimeoutError(AIGatewayError):
    """Raised when an AI provider request times out."""
    pass


class ProviderUnavailableError(AIGatewayError):
    """Raised when an AI provider returns HTTP 5xx or connection drops."""
    pass


class MalformedStructuredOutputError(AIGatewayError):
    """Raised when an AI provider returns unparseable or schema-violating output."""
    pass


class AuthenticationError(AIGatewayError):
    """Raised when an AI provider credentials are invalid (HTTP 401/403)."""
    pass


class ProviderConfigurationError(AIGatewayError):
    """Raised when an AI provider is called without required configuration."""
    pass


class AllProvidersFailedError(AIGatewayError):
    """Raised when primary and all fallback providers fail to generate response."""
    pass


# -------------------------------------------------------------
# Gateway Data Models
# -------------------------------------------------------------
class ProviderHealth(BaseModel):
    provider_name: str
    status: ProviderStatus
    is_configured: bool
    model_name: str
    cooldown_until: Optional[float] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    success_count: int = 0


class AIRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    images: Optional[List[bytes]] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    task_type: TaskType = TaskType.GENERAL
    # Expected structured output format or schema description
    schema_definition: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AttemptRecord(BaseModel):
    provider: str
    model: str
    latency_ms: float
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class AIResponse(BaseModel):
    content: str
    structured_data: Optional[Any] = None
    provider: str
    model: str
    latency_ms: float
    is_fallback: bool = False
    attempts_history: List[AttemptRecord] = Field(default_factory=list)
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None
