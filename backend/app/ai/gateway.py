import time
from typing import Dict, Any, List, Optional, Tuple

from backend.app.ai.types import (
    TaskType,
    AIRequest,
    AIResponse,
    AttemptRecord,
    ProviderStatus,
    ProviderHealth,
    AIGatewayError,
    RateLimitError,
    AITimeoutError,
    ProviderUnavailableError,
    MalformedStructuredOutputError,
    AuthenticationError,
    ProviderConfigurationError,
    AllProvidersFailedError,
)
from backend.app.ai.providers.base import BaseAIProvider
from backend.app.ai.providers.gemini_provider import GeminiProvider
from backend.app.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
from backend.app.ai.secret_masker import sanitize_text
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class AIGateway:
    """
    Multi-Model AI Gateway managing resilient model routing, automated failover,
    rate-limit cooldown tracking, and unified error handling across Gemini
    and OpenAI-compatible secondary providers.
    """

    def __init__(
        self,
        gemini_provider: Optional[BaseAIProvider] = None,
        secondary_provider: Optional[BaseAIProvider] = None,
    ):
        self.providers: Dict[str, BaseAIProvider] = {}

        # Default registered providers
        sec_provider = secondary_provider or OpenAICompatibleProvider()
        sec_key = sec_provider.provider_name or "openai_compatible"

        self.register_provider("gemini", gemini_provider or GeminiProvider())
        self.register_provider(sec_key, sec_provider)
        if sec_key != "openai_compatible":
            self.register_provider("openai_compatible", sec_provider)

        # Routing Table (Primary -> Fallback)
        self._routing_table: Dict[TaskType, Tuple[str, str]] = {
            TaskType.TUTOR: ("gemini", sec_key),
            TaskType.QUIZ: (sec_key, "gemini"),
            TaskType.FLASHCARDS: (sec_key, "gemini"),
            TaskType.GENERAL: ("gemini", sec_key),
        }

    def register_provider(self, name: str, provider: BaseAIProvider) -> None:
        """Registers an AI provider with the gateway."""
        self.providers[name] = provider
        logger.info(
            f"[AI Gateway] Registered provider '{name}' (model='{provider.model_name}', configured={provider.is_configured()})"
        )

    def get_provider(self, name: str) -> Optional[BaseAIProvider]:
        return self.providers.get(name)

    def get_routing_order(self, task_type: TaskType) -> List[str]:
        """
        Determines the priority order of providers for a given task type.
        If secondary is not configured, drops it gracefully so Gemini handles requests.
        """
        primary_name, fallback_name = self._routing_table.get(
            task_type, ("gemini", "openai_compatible")
        )

        candidates = [primary_name, fallback_name]
        # De-duplicate while preserving order
        ordered: List[str] = []
        for name in candidates:
            if name in self.providers and name not in ordered:
                ordered.append(name)
        return ordered

    def get_readiness_report(self) -> Dict[str, Any]:
        """
        Provides lightweight, secret-safe startup and readiness diagnostics
        for all registered providers.
        """
        provider_reports = {}
        any_healthy = False

        for name, provider in self.providers.items():
            health = provider.get_health()
            report = {
                "configured": health.is_configured,
                "status": health.status.value,
                "model": health.model_name,
                "consecutive_failures": health.consecutive_failures,
                "success_count": health.success_count,
            }
            if health.cooldown_until:
                remaining = max(0.0, round(health.cooldown_until - time.time(), 1))
                report["cooldown_remaining_seconds"] = remaining
            if health.last_error:
                report["last_error"] = health.last_error

            if health.is_configured and health.status != ProviderStatus.ERROR:
                any_healthy = True

            provider_reports[name] = report

        return {
            "gateway_status": "ready" if any_healthy else "degraded",
            "routing": {
                task.value: {
                    "primary": self._routing_table[task][0],
                    "fallback": self._routing_table[task][1],
                }
                for task in self._routing_table
            },
            "providers": provider_reports,
        }

    async def _execute_with_provider(
        self,
        provider: BaseAIProvider,
        request: AIRequest,
        is_structured: bool,
    ) -> AIResponse:
        """Executes generation against a single provider."""
        if is_structured:
            return await provider.generate_structured(request)
        return await provider.generate_text(request)

    async def generate_text(self, request: AIRequest) -> AIResponse:
        """Executes resilient text generation with automated failover."""
        return await self._dispatch_with_failover(request, is_structured=False)

    async def generate_structured(self, request: AIRequest) -> AIResponse:
        """Executes resilient structured JSON generation with automated failover."""
        return await self._dispatch_with_failover(request, is_structured=True)

    async def _dispatch_with_failover(
        self,
        request: AIRequest,
        is_structured: bool,
    ) -> AIResponse:
        """
        Dispatches request to providers based on routing priority.
        Preserves the exact same prompt, system instructions, and schema across failovers.
        """
        routing_order = self.get_routing_order(request.task_type)
        attempts_history: List[AttemptRecord] = []
        last_exception: Optional[Exception] = None

        for idx, provider_name in enumerate(routing_order):
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            is_fallback_attempt = idx > 0

            # 1. Check if provider is configured
            if not provider.is_configured():
                logger.info(
                    f"[AI Gateway] Provider '{provider_name}' is not configured. Skipping to next candidate."
                )
                attempts_history.append(
                    AttemptRecord(
                        provider=provider_name,
                        model=provider.model_name,
                        latency_ms=0.0,
                        success=False,
                        error_type="UNCONFIGURED",
                        error_message=f"Provider '{provider_name}' has no credentials configured.",
                    )
                )
                continue

            # 2. Check if provider is currently in cooldown (e.g. following a 429)
            if not provider.is_available():
                health = provider.get_health()
                remaining = (
                    round(health.cooldown_until - time.time(), 1)
                    if health.cooldown_until
                    else 0.0
                )
                logger.info(
                    f"[AI Gateway] Provider '{provider_name}' is in cooldown ({remaining}s remaining). Failing over."
                )
                attempts_history.append(
                    AttemptRecord(
                        provider=provider_name,
                        model=provider.model_name,
                        latency_ms=0.0,
                        success=False,
                        error_type="COOLDOWN",
                        error_message=f"Provider is in rate-limit cooldown ({remaining}s remaining).",
                    )
                )
                continue

            # 3. Attempt execution (with 1 bounded retry for timeout/malformed JSON)
            start_t = time.time()
            max_retries = 1
            for retry_num in range(max_retries + 1):
                try:
                    logger.debug(
                        f"[AI Gateway] Invoking '{provider_name}' for task '{request.task_type.value}' "
                        f"(fallback={is_fallback_attempt}, attempt={retry_num + 1})"
                    )

                    response = await self._execute_with_provider(
                        provider=provider,
                        request=request,
                        is_structured=is_structured,
                    )

                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    attempts_history.append(
                        AttemptRecord(
                            provider=provider_name,
                            model=provider.model_name,
                            latency_ms=lat_ms,
                            success=True,
                        )
                    )

                    response.is_fallback = is_fallback_attempt
                    response.attempts_history = attempts_history
                    return response

                except AITimeoutError as timeout_err:
                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    last_exception = timeout_err
                    if retry_num < max_retries:
                        logger.warning(
                            f"[AI Gateway] Provider '{provider_name}' timed out. Retrying once (attempt {retry_num + 2})..."
                        )
                        continue
                    else:
                        logger.warning(
                            f"[AI Gateway] Provider '{provider_name}' timed out after retry. Failing over."
                        )
                        attempts_history.append(
                            AttemptRecord(
                                provider=provider_name,
                                model=provider.model_name,
                                latency_ms=lat_ms,
                                success=False,
                                error_type="TIMEOUT",
                                error_message=str(timeout_err),
                            )
                        )
                        break

                except MalformedStructuredOutputError as json_err:
                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    last_exception = json_err
                    if retry_num < max_retries:
                        logger.warning(
                            f"[AI Gateway] Provider '{provider_name}' returned malformed JSON. Retrying once..."
                        )
                        continue
                    else:
                        logger.warning(
                            f"[AI Gateway] Provider '{provider_name}' returned malformed JSON after retry. Failing over."
                        )
                        attempts_history.append(
                            AttemptRecord(
                                provider=provider_name,
                                model=provider.model_name,
                                latency_ms=lat_ms,
                                success=False,
                                error_type="MALFORMED_OUTPUT",
                                error_message=str(json_err),
                            )
                        )
                        break

                except RateLimitError as rl_err:
                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    last_exception = rl_err
                    logger.warning(
                        f"[AI Gateway] Provider '{provider_name}' rate limited (429). Immediately failing over."
                    )
                    attempts_history.append(
                        AttemptRecord(
                            provider=provider_name,
                            model=provider.model_name,
                            latency_ms=lat_ms,
                            success=False,
                            error_type="RATE_LIMIT",
                            error_message=str(rl_err),
                        )
                    )
                    break

                except AuthenticationError as auth_err:
                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    last_exception = auth_err
                    logger.error(
                        f"[AI Gateway] Provider '{provider_name}' authentication failed. Failing over."
                    )
                    attempts_history.append(
                        AttemptRecord(
                            provider=provider_name,
                            model=provider.model_name,
                            latency_ms=lat_ms,
                            success=False,
                            error_type="AUTHENTICATION_ERROR",
                            error_message=str(auth_err),
                        )
                    )
                    break

                except Exception as gen_err:
                    lat_ms = round((time.time() - start_t) * 1000, 2)
                    last_exception = gen_err
                    logger.warning(
                        f"[AI Gateway] Provider '{provider_name}' failed with {type(gen_err).__name__}. Failing over."
                    )
                    attempts_history.append(
                        AttemptRecord(
                            provider=provider_name,
                            model=provider.model_name,
                            latency_ms=lat_ms,
                            success=False,
                            error_type="PROVIDER_ERROR",
                            error_message=str(gen_err),
                        )
                    )
                    break

        # 4. Emergency Final Fallback (All Providers Failed)
        summary_reasons = "; ".join(
            [f"{att.provider}: {att.error_type} ({att.error_message or 'failed'})" for att in attempts_history]
        )
        logger.error(f"[AI Gateway] ALL providers failed for task '{request.task_type.value}': {summary_reasons}")

        return AIResponse(
            content="⚠️ **AI Model Generation Temporarily Unavailable**\n\n"
                    "All configured AI providers are currently rate-limited, unreachable, or undergoing maintenance. "
                    "Please try again shortly.",
            structured_data=None,
            provider="none",
            model="none",
            latency_ms=0.0,
            is_fallback=True,
            attempts_history=attempts_history,
            error=f"All providers failed: {summary_reasons}",
        )


ai_gateway = AIGateway()
