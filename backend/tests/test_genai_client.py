"""
The Gemini adapter on the supported `google-genai` SDK: requests are formed as the Gemini API
expects (checked through a mock HTTP transport, no network), and errors keep their meaning.
"""
import asyncio
import json

import httpx
import pytest
from google import genai
from google.genai import types

from backend.app.ai import genai_client
from backend.app.ai.providers.gemini_provider import GeminiProvider
from backend.app.ai.types import AIRequest, RateLimitError, TaskType


def _client(key: str, handler):
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    genai_client._clients[key] = client
    return client


def test_generate_sends_system_prompt_json_mode_and_images():
    seen = []

    def handler(req: httpx.Request):
        seen.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}], "role": "model"}}]})

    _client("k-generate-0001", handler)
    out = genai_client.generate_content(
        "k-generate-0001", "models/gemini-3.8-flash", "Explain paging",
        system_instruction="You are a tutor", temperature=0.2, max_output_tokens=100,
        json_output=True, images=[b"png-bytes"],
    )
    assert out == '{"ok": true}'
    url, body = seen[0]
    assert url.endswith("/models/gemini-3.8-flash:generateContent")
    assert body["systemInstruction"]["parts"][0]["text"] == "You are a tutor"
    assert body["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 100, "responseMimeType": "application/json"}
    assert body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/png"


def test_embeddings_batch_and_single_shapes():
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append((str(req.url), body))
        return httpx.Response(200, json={"embeddings": [{"values": [0.5] * 768} for _ in body["requests"]]})

    _client("k-embed-00001", handler)
    batch = genai_client.embed_content("models/gemini-embedding-001", ["a", "b"], "retrieval_document", 768, api_key="k-embed-00001")
    assert len(batch["embedding"]) == 2 and len(batch["embedding"][0]) == 768
    req = seen[0][1]["requests"][0]
    assert req["taskType"] == "RETRIEVAL_DOCUMENT" and req["outputDimensionality"] == 768

    single = genai_client.embed_content("models/gemini-embedding-001", "query", "retrieval_query", 768, api_key="k-embed-00001")
    assert len(single["embedding"]) == 768 and isinstance(single["embedding"][0], float)
    assert seen[1][1]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_a_429_puts_gemini_in_cooldown_so_the_gateway_fails_over():
    def handler(req):
        return httpx.Response(429, json={"error": {"code": 429, "message": "Quota exhausted", "status": "RESOURCE_EXHAUSTED"}})

    _client("k-ratelimit-01", handler)
    provider = GeminiProvider(api_key="k-ratelimit-01")
    with pytest.raises(RateLimitError):
        asyncio.run(provider.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ)))
    assert provider.get_health().status.value == "cooldown"


HIGH_DEMAND = {"error": {"code": 503, "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.", "status": "UNAVAILABLE"}}


def test_high_demand_503_is_retried_and_then_succeeds(monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, json=HIGH_DEMAND)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}], "role": "model"}}]})

    client = genai.Client(
        api_key="k-overload-001",
        http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(
                attempts=genai_client.OVERLOAD_RETRY_ATTEMPTS, initial_delay=0.01, max_delay=0.02,
                http_status_codes=[500, 502, 503, 504],
            ),
        ),
    )
    genai_client._clients["k-overload-001"] = client
    assert genai_client.generate_content("k-overload-001", "gemini-3.8-flash", "hi") == "ok"
    assert len(calls) == 3


def test_retry_settings_cover_overload_but_not_quota():
    genai_client._clients.pop("k-settings-0001", None)
    opts = genai_client.get_client("k-settings-0001")._api_client._http_options.retry_options
    assert opts.attempts >= 3 and 503 in opts.http_status_codes and 429 not in opts.http_status_codes


def test_overload_after_retries_cools_gemini_down_so_the_gateway_fails_over():
    _client("k-overload-002", lambda req: httpx.Response(503, json=HIGH_DEMAND))
    provider = GeminiProvider(api_key="k-overload-002")
    from backend.app.ai.types import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(provider.generate_structured(AIRequest(prompt="x", task_type=TaskType.QUIZ)))
    health = provider.get_health()
    assert health.status.value == "cooldown"
    assert "high demand" in (health.last_error or "")
