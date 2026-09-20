import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from backend.app.ai.types import (
    AIRequest,
    AIResponse,
    ProviderHealth,
    ProviderStatus,
    RateLimitError,
    AITimeoutError,
    ProviderUnavailableError,
    MalformedStructuredOutputError,
    AuthenticationError,
    ProviderConfigurationError,
)
from backend.app.ai.secret_masker import sanitize_text
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class BaseAIProvider(ABC):
    """
    Abstract base class for all AI model providers.
    Tracks health, availability, rate-limit cooldown, and provides
    consistent text and structured generation interfaces.
    """

    def __init__(self, provider_name: str, model_name: str):
        self.provider_name = provider_name
        self.model_name = model_name
        self._cooldown_until: Optional[float] = None
        self._last_error: Optional[str] = None
        self._consecutive_failures: int = 0
        self._success_count: int = 0
        self._known_secrets: List[str] = []

    def register_secret(self, secret: Optional[str]) -> None:
        """Registers a secret key with the provider for automatic scrubbing in logs and errors."""
        if secret and len(secret) >= 6:
            self._known_secrets.append(secret)

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if required credentials and endpoints are present."""
        pass

    def is_available(self) -> bool:
        """
        Checks if provider is ready to receive requests:
        1. Must be configured.
        2. Must not be currently in rate-limit cooldown.
        """
        if not self.is_configured():
            return False

        if self._cooldown_until is not None:
            now = time.time()
            if now < self._cooldown_until:
                remaining = round(self._cooldown_until - now, 1)
                logger.debug(
                    f"[{self.provider_name}] Skipped: in cooldown for another {remaining}s."
                )
                return False
            else:
                # Cooldown expired, transition back to probation/healthy
                self._cooldown_until = None

        return True

    def mark_success(self) -> None:
        """Records a successful API interaction."""
        self._consecutive_failures = 0
        self._success_count += 1
        self._last_error = None
        self._cooldown_until = None

    def mark_rate_limited(self, cooldown_seconds: float = 60.0, error: str = "Rate limit reached") -> None:
        """Puts provider into temporary cooldown after receiving HTTP 429."""
        sanitized_err = sanitize_text(error, self._known_secrets)
        self._cooldown_until = time.time() + cooldown_seconds
        self._last_error = sanitized_err
        self._consecutive_failures += 1
        logger.warning(
            f"[{self.provider_name}] Marked in cooldown for {cooldown_seconds}s. Reason: {sanitized_err}"
        )

    def mark_failure(self, error: str) -> None:
        """Records an API failure other than rate limits."""
        sanitized_err = sanitize_text(error, self._known_secrets)
        self._consecutive_failures += 1
        self._last_error = sanitized_err
        logger.warning(
            f"[{self.provider_name}] Failure recorded (consecutive={self._consecutive_failures}): {sanitized_err}"
        )

    def get_health(self) -> ProviderHealth:
        """Returns current live health status without sensitive data."""
        if not self.is_configured():
            status = ProviderStatus.UNCONFIGURED
        elif self._cooldown_until and time.time() < self._cooldown_until:
            status = ProviderStatus.COOLDOWN
        elif self._consecutive_failures >= 3:
            status = ProviderStatus.ERROR
        else:
            status = ProviderStatus.HEALTHY

        return ProviderHealth(
            provider_name=self.provider_name,
            status=status,
            is_configured=self.is_configured(),
            model_name=self.model_name,
            cooldown_until=self._cooldown_until,
            last_error=self._last_error,
            consecutive_failures=self._consecutive_failures,
            success_count=self._success_count,
        )

    @abstractmethod
    async def generate_text(self, request: AIRequest) -> AIResponse:
        """Generates conversational text completion."""
        pass

    @abstractmethod
    async def generate_structured(self, request: AIRequest) -> AIResponse:
        """Generates structured JSON completion validated against schema/format."""
        pass
