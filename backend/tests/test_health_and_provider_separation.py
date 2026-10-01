import time
import pytest
from httpx import AsyncClient
from backend.app.ai.gateway import ai_gateway
from backend.app.ai.types import ProviderStatus


@pytest.fixture(autouse=True)
def configured_providers():
    """
    The cooldown scenarios below need providers that count as configured. Give any provider
    without a key a placeholder for the duration of the test (no network call is made), so
    these tests do not depend on real API keys being present in the environment.
    """
    saved = {}
    for name, provider in ai_gateway.providers.items():
        if hasattr(provider, "_api_key") and not provider.is_configured():
            saved[name] = provider._api_key
            provider._api_key = "test-placeholder-key"
    yield
    for name, key in saved.items():
        ai_gateway.providers[name]._api_key = key


@pytest.mark.asyncio
async def test_health_check_structure(async_client: AsyncClient):
    """Verifies complete health check structure separating backend and AI provider health."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["backend"] == "healthy"
    assert "service" in data
    assert "database" in data
    assert "ai" in data

    ai_data = data["ai"]
    assert "status" in ai_data
    assert "gateway_status" in ai_data
    assert "fallback_available" in ai_data
    assert ai_data["fallback_available"] is True
    assert "providers" in ai_data


@pytest.mark.asyncio
async def test_health_check_gemini_cooldown_keeps_backend_healthy(async_client: AsyncClient):
    """
    Critical Incident 1 & 2 verification:
    When Gemini enters 429 rate-limit cooldown, the FastAPI backend MUST NOT
    report 'Backend Offline'. Backend remains 'healthy', and AI is marked 'degraded'.
    """
    gemini_provider = ai_gateway.get_provider("gemini")
    original_cooldown = gemini_provider._cooldown_until
    original_error = gemini_provider._last_error

    try:
        # Simulate 429 cooldown on Gemini
        gemini_provider._cooldown_until = time.time() + 60.0
        gemini_provider._last_error = "Resource has been exhausted (e.g. check quota) - HTTP 429"

        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()

        # Backend process itself is HEALTHY
        assert data["backend"] == "healthy"
        assert data["status"] == "ok"

        # AI provider health reflects cooldown
        ai_data = data["ai"]
        assert ai_data["fallback_available"] is True
        gemini_report = ai_data["providers"].get("gemini", {})
        assert gemini_report.get("status") == "cooldown"
        assert gemini_report.get("cooldown_remaining_seconds", 0) > 0
    finally:
        gemini_provider._cooldown_until = original_cooldown
        gemini_provider._last_error = original_error


@pytest.mark.asyncio
async def test_health_check_all_providers_cooldown_keeps_backend_healthy(async_client: AsyncClient):
    """
    When ALL AI providers are in cooldown (e.g., both Gemini & OpenRouter quota exhausted),
    FastAPI backend is STILL healthy and operational with retrieval fallback available.
    """
    saved_state = {}
    for name, provider in ai_gateway.providers.items():
        saved_state[name] = (provider._cooldown_until, provider._last_error)

    try:
        now = time.time()
        for name, provider in ai_gateway.providers.items():
            provider._cooldown_until = now + 120.0
            provider._last_error = f"{name} simulated 429 rate limit"

        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()

        # Backend is 100% HEALTHY
        assert data["backend"] == "healthy"
        assert data["status"] == "ok"

        # AI status is DEGRADED, NOT UNAVAILABLE, because grounded fallback is active
        ai_data = data["ai"]
        assert ai_data["status"] == "degraded"
        assert ai_data["fallback_available"] is True
    finally:
        for name, (cd, err) in saved_state.items():
            if name in ai_gateway.providers:
                ai_gateway.providers[name]._cooldown_until = cd
                ai_gateway.providers[name]._last_error = err


@pytest.mark.asyncio
async def test_ai_provider_cooldown_does_not_mask_real_errors(async_client: AsyncClient):
    """Verifies that cooldown error details are safely sanitized and visible in diagnostics."""
    gemini_provider = ai_gateway.get_provider("gemini")
    original_cooldown = gemini_provider._cooldown_until
    original_error = gemini_provider._last_error

    try:
        gemini_provider._cooldown_until = time.time() + 45.0
        gemini_provider._last_error = "Rate limit exceeded (HTTP 429)"

        report = ai_gateway.get_readiness_report()
        gemini_rep = report["providers"]["gemini"]
        assert gemini_rep["status"] == ProviderStatus.COOLDOWN.value
        assert "429" in gemini_rep["last_error"]
        assert gemini_rep["cooldown_remaining_seconds"] > 0
    finally:
        gemini_provider._cooldown_until = original_cooldown
        gemini_provider._last_error = original_error
