import json
import re
import time
from typing import Optional, Dict, Any, List

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


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider implementation supporting text, vision,
    and structured JSON generation with comprehensive error classification.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        raw_model = model_name or settings.gemini_model or "gemini-3.8-flash"
        effective_model = self._resolve_model_name(raw_model)
        super().__init__(provider_name="gemini", model_name=effective_model)

        if self._api_key:
            self.register_secret(self._api_key)
        self._configured = False

    @staticmethod
    def _resolve_model_name(raw_model: str) -> str:
        """
        Normalizes model identifier to gemini-3.8-flash standard format for Google SDK.
        Strictly rejects obsolete legacy models instead of silently substituting them.
        """
        if not raw_model:
            return "gemini-3.8-flash"

        trimmed = raw_model.strip()
        lower = trimmed.lower()

        # Fail fast: Reject obsolete or legacy Gemini models
        if any(legacy in lower for legacy in ["3.6", "2.5", "1.5", "1.0", "pro-vision"]):
            raise ProviderConfigurationError(
                f"Obsolete or prohibited Gemini generation model '{trimmed}' requested. "
                f"Silent substitution of legacy models is strictly prohibited. "
                f"LumoraAI requires 'models/gemini-3.8-flash'.",
                provider="gemini",
            )

        # Normalize models/ prefix for SDK
        normalized = trimmed.replace("models/", "")
        if normalized != "gemini-3.8-flash":
            raise ProviderConfigurationError(
                f"Unsupported Gemini generation model '{trimmed}'. "
                f"LumoraAI strictly expects 'models/gemini-3.8-flash' or 'gemini-3.8-flash'.",
                provider="gemini",
            )

        return normalized

    def is_configured(self) -> bool:
        return bool(self._api_key and len(self._api_key.strip()) >= 10)

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise ProviderConfigurationError(
                "Gemini API key is not configured or is empty.", provider=self.provider_name
            )
        if not self._configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._configured = True
            except Exception as e:
                sanitized_msg = sanitize_text(str(e), self._known_secrets)
                raise ProviderConfigurationError(
                    f"Failed to configure Gemini SDK: {sanitized_msg}", provider=self.provider_name
                )

    def _classify_error(self, e: Exception) -> Exception:
        err_str = str(e)
        sanitized_msg = sanitize_text(err_str, self._known_secrets)
        lower_err = err_str.lower()

        # 1. Rate Limit (HTTP 429 / Quota)
        if any(w in lower_err for w in ["429", "resource_exhausted", "quota", "rate limit"]):
            self.mark_rate_limited(cooldown_seconds=60.0, error=sanitized_msg)
            return RateLimitError(f"Gemini quota exceeded or rate limit reached: {sanitized_msg}", provider=self.provider_name)

        # 2. Timeout
        if any(w in lower_err for w in ["timeout", "timed out", "deadline_exceeded", "timedout"]):
            self.mark_failure(sanitized_msg)
            return AITimeoutError(f"Gemini generation timed out: {sanitized_msg}", provider=self.provider_name)

        # 3. Authentication / Key validity
        if any(w in lower_err for w in ["401", "403", "api key not valid", "permission_denied", "invalid_argument"]):
            self.mark_failure(sanitized_msg)
            return AuthenticationError(f"Gemini authentication failed: {sanitized_msg}", provider=self.provider_name)

        # 4. Service Unavailable / Internal error
        if any(w in lower_err for w in ["500", "503", "unavailable", "internal", "connection error"]):
            self.mark_failure(sanitized_msg)
            return ProviderUnavailableError(f"Gemini service unavailable: {sanitized_msg}", provider=self.provider_name)

        self.mark_failure(sanitized_msg)
        return ProviderUnavailableError(f"Gemini error: {sanitized_msg}", provider=self.provider_name)

    async def generate_text(self, request: AIRequest) -> AIResponse:
        self._ensure_configured()
        start_time = time.time()

        try:
            import google.generativeai as genai

            # Build generation config with validated Gemini 3.8 parameters
            gen_config: Dict[str, Any] = {}
            if request.temperature is not None:
                gen_config["temperature"] = float(request.temperature)
            if request.max_tokens is not None:
                gen_config["max_output_tokens"] = int(request.max_tokens)

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=request.system_prompt if request.system_prompt else None,
                generation_config=gen_config or None,
            )

            # Multimodal support: image bytes + text prompt
            if request.images and len(request.images) > 0:
                contents: List[Any] = [request.prompt]
                for img_bytes in request.images:
                    contents.append({"mime_type": "image/png", "data": img_bytes})
            else:
                contents = request.prompt

            response = model.generate_content(contents)

            if not response or not hasattr(response, "text") or not response.text:
                raise ProviderUnavailableError("Gemini returned empty text response.", provider=self.provider_name)

            latency_ms = round((time.time() - start_time) * 1000, 2)
            self.mark_success()

            return AIResponse(
                content=response.text.strip(),
                structured_data=None,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency_ms,
                is_fallback=False,
            )

        except Exception as e:
            classified = self._classify_error(e)
            raise classified from e

    async def generate_structured(self, request: AIRequest) -> AIResponse:
        self._ensure_configured()
        start_time = time.time()

        try:
            import google.generativeai as genai

            gen_config: Dict[str, Any] = {
                "response_mime_type": "application/json"
            }
            if request.temperature is not None:
                gen_config["temperature"] = float(request.temperature)
            if request.max_tokens is not None:
                gen_config["max_output_tokens"] = int(request.max_tokens)

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=request.system_prompt if request.system_prompt else None,
                generation_config=gen_config,
            )

            prompt = request.prompt
            if request.schema_definition:
                prompt += f"\n\nOutput MUST strictly conform to this JSON schema:\n{json.dumps(request.schema_definition)}"

            if request.images and len(request.images) > 0:
                contents: List[Any] = [prompt]
                for img_bytes in request.images:
                    contents.append({"mime_type": "image/png", "data": img_bytes})
            else:
                contents = prompt

            response = model.generate_content(contents)

            if not response or not hasattr(response, "text") or not response.text:
                raise ProviderUnavailableError("Gemini returned empty structured response.", provider=self.provider_name)

            raw_text = response.text.strip()
            # Clean possible markdown fence blocks
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text).strip()

            try:
                parsed_json = json.loads(raw_text)
            except Exception as json_err:
                sanitized_raw = sanitize_text(raw_text[:200], self._known_secrets)
                raise MalformedStructuredOutputError(
                    f"Gemini returned invalid JSON: {json_err} | Text preview: {sanitized_raw}",
                    provider=self.provider_name,
                ) from json_err

            latency_ms = round((time.time() - start_time) * 1000, 2)
            self.mark_success()

            return AIResponse(
                content=raw_text,
                structured_data=parsed_json,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=latency_ms,
                is_fallback=False,
            )

        except MalformedStructuredOutputError:
            self.mark_failure("Malformed JSON output")
            raise
        except Exception as e:
            classified = self._classify_error(e)
            raise classified from e
