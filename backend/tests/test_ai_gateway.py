import time
import pytest
from typing import Optional, Dict, Any, List

from backend.app.ai.types import (
    TaskType,
    AIRequest,
    AIResponse,
    ProviderStatus,
    RateLimitError,
    AITimeoutError,
    ProviderUnavailableError,
    MalformedStructuredOutputError,
    AuthenticationError,
)
from backend.app.ai.providers.base import BaseAIProvider
from backend.app.ai.gateway import AIGateway
from backend.app.ai.secret_masker import sanitize_text


class MockProvider(BaseAIProvider):
    """Configurable mock AI provider for testing gateway routing and failover."""

    def __init__(
        self,
        provider_name: str,
        model_name: str = "mock-model",
        configured: bool = True,
    ):
        super().__init__(provider_name=provider_name, model_name=model_name)
        self._configured = configured
        self.text_responses: List[Any] = []
        self.structured_responses: List[Any] = []
        self.call_count: int = 0
        self.last_received_request: Optional[AIRequest] = None

    def is_configured(self) -> bool:
        return self._configured

    def queue_text_response(self, response_or_exception: Any) -> None:
        self.text_responses.append(response_or_exception)

    def queue_structured_response(self, response_or_exception: Any) -> None:
        self.structured_responses.append(response_or_exception)

    async def generate_text(self, request: AIRequest) -> AIResponse:
        self.call_count += 1
        self.last_received_request = request

        if not self.text_responses:
            self.mark_success()
            return AIResponse(
                content=f"Default text from {self.provider_name}",
                structured_data=None,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=10.0,
            )

        item = self.text_responses.pop(0)
        if isinstance(item, Exception):
            if isinstance(item, RateLimitError):
                self.mark_rate_limited(cooldown_seconds=60.0, error=str(item))
            else:
                self.mark_failure(str(item))
            raise item

        self.mark_success()
        return AIResponse(
            content=str(item),
            structured_data=None,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=15.0,
        )

    async def generate_structured(self, request: AIRequest) -> AIResponse:
        self.call_count += 1
        self.last_received_request = request

        if not self.structured_responses:
            self.mark_success()
            return AIResponse(
                content='{"default": true}',
                structured_data={"default": True},
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=12.0,
            )

        item = self.structured_responses.pop(0)
        if isinstance(item, Exception):
            if isinstance(item, RateLimitError):
                self.mark_rate_limited(cooldown_seconds=60.0, error=str(item))
            else:
                self.mark_failure(str(item))
            raise item

        self.mark_success()
        return AIResponse(
            content=str(item),
            structured_data=item if isinstance(item, dict) else {"data": item},
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=18.0,
        )


@pytest.fixture
def mock_gemini():
    return MockProvider("gemini", "gemini-2.5-flash", configured=True)


@pytest.fixture
def mock_secondary():
    return MockProvider("openai_compatible", "gpt-4o-mini", configured=True)


@pytest.fixture
def gateway(mock_gemini, mock_secondary):
    return AIGateway(gemini_provider=mock_gemini, secondary_provider=mock_secondary)


@pytest.mark.asyncio
async def test_gemini_success(gateway, mock_gemini, mock_secondary):
    """Scenario 1: Primary provider (Gemini for Tutor) succeeds cleanly."""
    mock_gemini.queue_text_response("Synchronous consensus requires round-by-round coordination.")
    request = AIRequest(
        prompt="Explain synchronous consensus.",
        system_instruction="Be concise.",
        task_type=TaskType.TUTOR,
    )

    response = await gateway.generate_text(request)

    assert response.provider == "gemini"
    assert response.is_fallback is False
    assert "Synchronous consensus" in response.content
    assert len(response.attempts_history) == 1
    assert response.attempts_history[0].success is True
    assert mock_gemini.call_count == 1
    assert mock_secondary.call_count == 0


@pytest.mark.asyncio
async def test_secondary_provider_success(gateway, mock_gemini, mock_secondary):
    """Scenario 2: Primary provider (Secondary for Quiz) succeeds cleanly."""
    quiz_data = {"questions": [{"id": 1, "prompt": "What is 2+2?"}]}
    mock_secondary.queue_structured_response(quiz_data)
    request = AIRequest(
        prompt="Generate a math quiz question.",
        task_type=TaskType.QUIZ,
    )

    response = await gateway.generate_structured(request)

    assert response.provider == "openai_compatible"
    assert response.is_fallback is False
    assert response.structured_data == quiz_data
    assert len(response.attempts_history) == 1
    assert response.attempts_history[0].success is True
    assert mock_secondary.call_count == 1
    assert mock_gemini.call_count == 0


@pytest.mark.asyncio
async def test_gemini_429_failover(gateway, mock_gemini, mock_secondary):
    """Scenario 3: Gemini returns 429 -> immediately enters cooldown and falls back to secondary without retry."""
    mock_gemini.queue_text_response(RateLimitError("429 ResourceExhausted: quota exceeded"))
    mock_secondary.queue_text_response("Fallback response from secondary provider.")
    request = AIRequest(
        prompt="Explain deadlock conditions.",
        task_type=TaskType.TUTOR,
    )

    response = await gateway.generate_text(request)

    # Failed over to secondary
    assert response.provider == "openai_compatible"
    assert response.is_fallback is True
    assert "Fallback response" in response.content
    # Exactly 1 call to Gemini (no retry on 429)
    assert mock_gemini.call_count == 1
    assert mock_secondary.call_count == 1

    # Gemini must now be in cooldown
    assert mock_gemini.is_available() is False
    health = mock_gemini.get_health()
    assert health.status == ProviderStatus.COOLDOWN
    assert health.cooldown_until is not None
    assert health.cooldown_until > time.time()

    # Verify attempt history recorded 429 properly
    assert len(response.attempts_history) == 2
    assert response.attempts_history[0].provider == "gemini"
    assert response.attempts_history[0].success is False
    assert response.attempts_history[0].error_type == "RATE_LIMIT"
    assert response.attempts_history[1].provider == "openai_compatible"
    assert response.attempts_history[1].success is True


@pytest.mark.asyncio
async def test_gemini_timeout_failover(gateway, mock_gemini, mock_secondary):
    """Scenario 4: Gemini times out -> 1 retry on Gemini -> then falls back to secondary."""
    # First attempt times out, second attempt (retry) also times out
    mock_gemini.queue_text_response(AITimeoutError("Request timed out after 30s"))
    mock_gemini.queue_text_response(AITimeoutError("Request timed out after 30s"))
    mock_secondary.queue_text_response("Secondary provider answered after Gemini timed out.")

    request = AIRequest(
        prompt="Explain quicksort.",
        task_type=TaskType.TUTOR,
    )

    response = await gateway.generate_text(request)

    assert response.provider == "openai_compatible"
    assert response.is_fallback is True
    assert "Gemini timed out" in response.content
    # Gemini called twice (initial + 1 bounded retry)
    assert mock_gemini.call_count == 2
    assert mock_secondary.call_count == 1

    # History shows Gemini failed with TIMEOUT and secondary succeeded
    assert len(response.attempts_history) == 2
    assert response.attempts_history[0].error_type == "TIMEOUT"
    assert response.attempts_history[1].success is True


@pytest.mark.asyncio
async def test_secondary_failure_gemini_fallback(gateway, mock_gemini, mock_secondary):
    """Scenario 5: Quiz task routes to secondary first; secondary fails (500), falls back to Gemini."""
    mock_secondary.queue_structured_response(ProviderUnavailableError("500 Internal Server Error"))
    gemini_data = {"quiz": [{"q": "Explain virtual memory"}]}
    mock_gemini.queue_structured_response(gemini_data)

    request = AIRequest(
        prompt="Generate OS quiz.",
        task_type=TaskType.QUIZ,
    )

    response = await gateway.generate_structured(request)

    assert response.provider == "gemini"
    assert response.is_fallback is True
    assert response.structured_data == gemini_data
    assert mock_secondary.call_count == 1
    assert mock_gemini.call_count == 1
    assert response.attempts_history[0].provider == "openai_compatible"
    assert response.attempts_history[0].success is False
    assert response.attempts_history[1].provider == "gemini"
    assert response.attempts_history[1].success is True


@pytest.mark.asyncio
async def test_both_providers_failing_emergency_response(gateway, mock_gemini, mock_secondary):
    """Scenario 6: Both providers fail -> emergency truthful response returned without hallucination."""
    mock_gemini.queue_text_response(RateLimitError("Gemini quota 429"))
    mock_secondary.queue_text_response(ProviderUnavailableError("Secondary endpoint 503"))

    request = AIRequest(
        prompt="Explain B-trees.",
        task_type=TaskType.TUTOR,
    )

    response = await gateway.generate_text(request)

    assert response.provider == "none"
    assert response.is_fallback is True
    assert "AI Model Generation Temporarily Unavailable" in response.content
    assert response.structured_data is None
    assert response.error is not None
    assert len(response.attempts_history) == 2
    assert response.attempts_history[0].provider == "gemini"
    assert response.attempts_history[1].provider == "openai_compatible"


@pytest.mark.asyncio
async def test_malformed_json_retry_and_fallback(gateway, mock_gemini, mock_secondary):
    """Scenario 7: Primary returns malformed JSON -> retries once -> falls back to secondary."""
    # Secondary is primary for FLASHCARDS
    mock_secondary.queue_structured_response(
        MalformedStructuredOutputError("Failed to parse JSON: invalid char")
    )
    mock_secondary.queue_structured_response(
        MalformedStructuredOutputError("Failed to parse JSON: invalid char")
    )
    valid_flashcards = {"cards": [{"front": "Mutex", "back": "Mutual exclusion lock"}]}
    mock_gemini.queue_structured_response(valid_flashcards)

    request = AIRequest(
        prompt="Generate flashcards for synchronization primitives.",
        task_type=TaskType.FLASHCARDS,
    )

    response = await gateway.generate_structured(request)

    assert response.provider == "gemini"
    assert response.is_fallback is True
    assert response.structured_data == valid_flashcards
    # Secondary called twice due to 1 retry on malformed JSON
    assert mock_secondary.call_count == 2
    assert mock_gemini.call_count == 1
    assert response.attempts_history[0].error_type == "MALFORMED_OUTPUT"
    assert response.attempts_history[1].success is True


@pytest.mark.asyncio
async def test_cooldown_skips_provider(gateway, mock_gemini, mock_secondary):
    """Scenario 8: Provider in cooldown is immediately skipped on subsequent requests."""
    # Put Gemini in cooldown
    mock_gemini.mark_rate_limited(cooldown_seconds=60.0, error="Manual 429")
    mock_gemini.call_count = 0  # reset count

    mock_secondary.queue_text_response("Answered while Gemini in cooldown.")

    request = AIRequest(
        prompt="Explain paging.",
        task_type=TaskType.TUTOR,
    )

    response = await gateway.generate_text(request)

    # Gemini was skipped without calling generate_text
    assert mock_gemini.call_count == 0
    assert mock_secondary.call_count == 1
    assert response.provider == "openai_compatible"
    assert response.is_fallback is True
    assert response.attempts_history[0].provider == "gemini"
    assert response.attempts_history[0].error_type == "COOLDOWN"


def test_secret_masker_and_safe_logging():
    """Scenario 9: Validate secret masking on API keys and Bearer tokens."""
    sensitive_raw = (
        "Error contacting OpenAI with key sk-1234567890abcdef1234567890abcdef "
        "and Gemini key AIzaSyD9876543210zyxwvu and Bearer secret_token_xyz"
    )

    masked = sanitize_text(sensitive_raw, known_secrets=["secret_token_xyz"])

    assert "sk-1234567890abcdef1234567890abcdef" not in masked
    assert "AIzaSyD9876543210zyxwvu" not in masked
    assert "secret_token_xyz" not in masked
    assert "sk-..." in masked
    assert "AIz..." in masked


@pytest.mark.asyncio
async def test_boot_without_secondary_provider():
    """Scenario 10: Unconfigured secondary provider is gracefully skipped without crashing."""
    gemini = MockProvider("gemini", configured=True)
    gemini.queue_text_response("Gemini handles request directly.")

    unconfigured_secondary = MockProvider("openai_compatible", configured=False)

    gw = AIGateway(gemini_provider=gemini, secondary_provider=unconfigured_secondary)

    # Readiness report shows degraded secondary but overall ready gateway
    report = gw.get_readiness_report()
    assert report["gateway_status"] == "ready"
    assert report["providers"]["openai_compatible"]["configured"] is False
    assert report["providers"]["gemini"]["configured"] is True

    # Tutor request goes straight to Gemini
    request_tutor = AIRequest(prompt="What is a process?", task_type=TaskType.TUTOR)
    res_tutor = await gw.generate_text(request_tutor)
    assert res_tutor.provider == "gemini"
    assert res_tutor.is_fallback is False

    # Quiz request (primary is openai_compatible) skips unconfigured secondary and falls back to Gemini
    gemini.queue_structured_response({"quiz_ready": True})
    request_quiz = AIRequest(prompt="Generate quiz", task_type=TaskType.QUIZ)
    res_quiz = await gw.generate_structured(request_quiz)
    assert res_quiz.provider == "gemini"
    assert res_quiz.is_fallback is True
    assert res_quiz.attempts_history[0].error_type == "UNCONFIGURED"
    assert res_quiz.attempts_history[1].success is True
