"""
The OpenAI-compatible backup provider (Groq, OpenRouter...) always sends an answer-length limit,
waits as long as the provider asks after a 429, and reports a too-large request clearly.
"""
import json

import httpx
import pytest

from backend.app.ai.providers import openai_compatible_provider as mod
from backend.app.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
from backend.app.ai.types import AIRequest, RateLimitError, TaskType, ProviderUnavailableError
from backend.app.core.config import settings


def _provider(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return OpenAICompatibleProvider(api_key="gsk_test_key_123456", base_url="https://api.groq.com/openai/v1",
                                    model_name="llama-3.3-70b-versatile", provider_name="groq")


def _ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.mark.asyncio
async def test_max_tokens_is_always_sent(monkeypatch):
    seen = []

    def handler(req):
        seen.append(json.loads(req.content))
        return _ok('{"ok": true}')

    p = _provider(monkeypatch, handler)
    await p.generate_structured(AIRequest(prompt="x", task_type=TaskType.FLASHCARDS))
    await p.generate_text(AIRequest(prompt="x", task_type=TaskType.TUTOR))
    await p.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ, max_tokens=99999))
    assert [b["max_tokens"] for b in seen] == [settings.secondary_ai_max_tokens] * 3
    await p.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ, max_tokens=800))
    assert seen[-1]["max_tokens"] == 800


def test_timeout_comes_from_settings():
    p = OpenAICompatibleProvider(api_key="gsk_test_key_123456")
    assert p.timeout_seconds == settings.secondary_ai_timeout_seconds >= 60


@pytest.mark.asyncio
async def test_429_waits_as_long_as_groq_asks(monkeypatch):
    body = {"error": {"message": "Rate limit reached for model `llama-3.3-70b-versatile` on tokens per minute (TPM): Limit 12000, Used 11000, Requested 3000. Please try again in 7.66s.", "type": "tokens", "code": "rate_limit_exceeded"}}
    p = _provider(monkeypatch, lambda req: httpx.Response(429, json=body))
    with pytest.raises(RateLimitError):
        await p.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ))
    remaining = p._cooldown_until - __import__("time").time()
    assert 5 < remaining < 12


def test_retry_after_parsing():
    assert mod._retry_after_seconds("Please try again in 1m3.5s.") == pytest.approx(64.5)
    assert mod._retry_after_seconds("no hint here") == 60.0


@pytest.mark.asyncio
async def test_request_too_large_is_reported_clearly(monkeypatch):
    body = {"error": {"message": "Request too large for model `llama-3.3-70b-versatile` on tokens per minute (TPM): Limit 12000, Requested 40000", "code": "rate_limit_exceeded"}}
    p = _provider(monkeypatch, lambda req: httpx.Response(413, json=body))
    with pytest.raises(ProviderUnavailableError) as e:
        await p.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ))
    assert "too large" in str(e.value)
