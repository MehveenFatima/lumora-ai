import json
import re
import time
from typing import Optional, Dict, Any, List

import httpx

from backend.app.ai.providers.base import BaseAIProvider
from backend.app.ai.types import (
    AIRequest,
    AIResponse,
    RateLimitError,
    AITimeoutError,
    ProviderUnavailableError,
    MalformedStructuredOutputError,
    AuthenticationError,
    ProviderConfigurationError,
)
from backend.app.ai.secret_masker import sanitize_text
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider(BaseAIProvider):
    """
    OpenAI-compatible REST provider implementation (works with OpenAI,
    Groq, OpenRouter, DeepSeek, LocalAI, Ollama, vLLM).
    Uses standard POST /chat/completions with Bearer authorization and JSON mode.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        self._api_key = api_key if api_key is not None else settings.effective_secondary_api_key
        self._base_url = (base_url or settings.effective_secondary_base_url).rstrip("/")
        effective_model = model_name or settings.effective_secondary_model
        self.timeout_seconds = timeout_seconds
        resolved_provider_name = provider_name or settings.secondary_ai_provider_name or "openrouter"

        super().__init__(provider_name=resolved_provider_name, model_name=effective_model)

        if self._api_key:
            self.register_secret(self._api_key)

    def is_configured(self) -> bool:
        return bool(self._api_key and len(self._api_key.strip()) >= 5 and self._base_url)

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise ProviderConfigurationError(
                f"Secondary provider '{self.provider_name}' is not configured (missing OPENROUTER_API_KEY or SECONDARY_AI_API_KEY).",
                provider=self.provider_name,
            )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lumora.ai",
            "X-Title": "LumoraAI",
        }

    def _get_endpoint_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"

    def _classify_http_status(self, status_code: int, response_text: str) -> Exception:
        sanitized_msg = sanitize_text(response_text, self._known_secrets)

        if status_code == 429:
            self.mark_rate_limited(cooldown_seconds=60.0, error=sanitized_msg)
            return RateLimitError(
                f"Secondary provider rate limit exceeded (HTTP 429): {sanitized_msg}",
                provider=self.provider_name,
            )
        elif status_code in [401, 403]:
            self.mark_failure(sanitized_msg)
            return AuthenticationError(
                f"Secondary provider authentication failure (HTTP {status_code}): {sanitized_msg}",
                provider=self.provider_name,
            )
        elif status_code >= 500:
            self.mark_failure(sanitized_msg)
            return ProviderUnavailableError(
                f"Secondary provider service error (HTTP {status_code}): {sanitized_msg}",
                provider=self.provider_name,
            )
        else:
            self.mark_failure(sanitized_msg)
            return ProviderUnavailableError(
                f"Secondary provider request failed (HTTP {status_code}): {sanitized_msg}",
                provider=self.provider_name,
            )

    def _classify_network_exception(self, e: Exception) -> Exception:
        sanitized_err = sanitize_text(str(e), self._known_secrets)

        if isinstance(e, (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)):
            self.mark_failure(f"Timeout: {sanitized_err}")
            return AITimeoutError(
                f"Secondary provider timed out after {self.timeout_seconds}s: {sanitized_err}",
                provider=self.provider_name,
            )
        elif isinstance(e, (httpx.NetworkError, httpx.ConnectError)):
            self.mark_failure(f"Connection error: {sanitized_err}")
            return ProviderUnavailableError(
                f"Secondary provider network connection error: {sanitized_err}",
                provider=self.provider_name,
            )

        self.mark_failure(sanitized_err)
        return ProviderUnavailableError(
            f"Secondary provider network failure: {sanitized_err}",
            provider=self.provider_name,
        )

    async def generate_text(self, request: AIRequest) -> AIResponse:
        self._ensure_configured()
        start_time = time.time()

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        url = self._get_endpoint_url()
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code != 200:
                classified = self._classify_http_status(resp.status_code, resp.text)
                raise classified

            data = resp.json()
            choices = data.get("choices") or []
            if not choices or not choices[0].get("message", {}).get("content"):
                raise ProviderUnavailableError(
                    "Secondary provider returned empty choices in response.", provider=self.provider_name
                )

            content = choices[0]["message"]["content"].strip()
            latency_ms = round((time.time() - start_time) * 1000, 2)
            self.mark_success()

            usage = data.get("usage")

            return AIResponse(
                content=content,
                structured_data=None,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency_ms,
                token_usage=usage,
                is_fallback=False,
            )

        except (RateLimitError, AuthenticationError, ProviderUnavailableError, AITimeoutError):
            raise
        except Exception as e:
            classified = self._classify_network_exception(e)
            raise classified from e

    async def generate_structured(self, request: AIRequest) -> AIResponse:
        self._ensure_configured()
        start_time = time.time()

        system_instruction = request.system_prompt or "You are an expert AI tutor. Respond in valid JSON format."
        if request.schema_definition:
            system_instruction += f"\n\nYou MUST return valid JSON matching this schema:\n{json.dumps(request.schema_definition)}"
        else:
            system_instruction += "\n\nYou MUST respond with valid RFC 8259 JSON only."

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": request.prompt},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        url = self._get_endpoint_url()
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code != 200:
                classified = self._classify_http_status(resp.status_code, resp.text)
                raise classified

            data = resp.json()
            choices = data.get("choices") or []
            if not choices or not choices[0].get("message", {}).get("content"):
                raise ProviderUnavailableError(
                    "Secondary provider returned empty structured completion.", provider=self.provider_name
                )

            raw_text = choices[0]["message"]["content"].strip()
            # Strip potential code fences
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text).strip()

            try:
                parsed_json = json.loads(raw_text)
            except Exception as json_err:
                sanitized_raw = sanitize_text(raw_text[:200], self._known_secrets)
                raise MalformedStructuredOutputError(
                    f"Secondary provider returned invalid JSON: {json_err} | Preview: {sanitized_raw}",
                    provider=self.provider_name,
                ) from json_err

            latency_ms = round((time.time() - start_time) * 1000, 2)
            self.mark_success()
            usage = data.get("usage")

            return AIResponse(
                content=raw_text,
                structured_data=parsed_json,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency_ms,
                token_usage=usage,
                is_fallback=False,
            )

        except MalformedStructuredOutputError:
            self.mark_failure("Malformed JSON output")
            raise
        except (RateLimitError, AuthenticationError, ProviderUnavailableError, AITimeoutError):
            raise
        except Exception as e:
            classified = self._classify_network_exception(e)
            raise classified from e
