import pytest
from pydantic import ValidationError
from backend.app.core.config import Settings
from backend.app.ai.providers.gemini_provider import GeminiProvider
from backend.app.ai.types import ProviderConfigurationError, AIRequest, TaskType
from backend.app.ai.gateway import AIGateway


def test_config_defaults_to_gemini_3_8():
    """Verify Settings class defaults to models/gemini-3.8-flash."""
    s = Settings()
    assert s.gemini_model in ("models/gemini-3.8-flash", "gemini-3.8-flash")
    assert "3.8" in s.gemini_model
    assert "3.6" not in s.gemini_model


def test_config_rejects_legacy_3_6_and_obsolete_models():
    """Verify Settings field validator rejects legacy models (3.6, 2.5, 1.5) with ValueError."""
    for obsolete in ["gemini-3.6-flash", "models/gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-pro"]:
        with pytest.raises(ValidationError) as excinfo:
            Settings(GEMINI_MODEL=obsolete)
        err_str = str(excinfo.value)
        assert "Obsolete or prohibited Gemini generation model" in err_str or "Unsupported" in err_str


def test_provider_normalizes_models_prefix():
    """Verify GeminiProvider._resolve_model_name strips 'models/' prefix for Google SDK."""
    resolved = GeminiProvider._resolve_model_name("models/gemini-3.8-flash")
    assert resolved == "gemini-3.8-flash"

    resolved_plain = GeminiProvider._resolve_model_name("gemini-3.8-flash")
    assert resolved_plain == "gemini-3.8-flash"


def test_provider_rejects_obsolete_model_without_silent_substitution():
    """Verify GeminiProvider strictly raises ProviderConfigurationError for legacy models."""
    for obsolete in ["gemini-3.6-flash", "models/gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
        with pytest.raises(ProviderConfigurationError) as excinfo:
            GeminiProvider._resolve_model_name(obsolete)
        assert "Obsolete or prohibited Gemini generation model" in str(excinfo.value)


def test_gateway_tutor_routing_model_identifier():
    """Verify Inherited Gateway Tutor routing assigns Gemini provider with model gemini-3.8-flash."""
    provider = GeminiProvider(api_key="test_dummy_key_12345", model_name="models/gemini-3.8-flash")
    assert provider.model_name == "gemini-3.8-flash"

    gw = AIGateway(gemini_provider=provider)
    effective_gemini = gw.get_provider("gemini")
    assert effective_gemini is not None
    assert effective_gemini.model_name == "gemini-3.8-flash"

    order = gw.get_routing_order(TaskType.TUTOR)
    assert order[0] == "gemini"


def test_embedding_model_and_dimensions_invariable():
    """Verify embedding model remains models/gemini-embedding-001 with 768 dimensions."""
    s = Settings()
    assert s.gemini_embedding_model == "models/gemini-embedding-001"
    assert s.embedding_dimensions == 768

    # Ensure tampering is rejected
    with pytest.raises(ValidationError):
        Settings(GEMINI_EMBEDDING_MODEL="models/text-embedding-004")

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_DIMENSIONS=1536)


def test_openrouter_secondary_config_preserved():
    """Verify OpenRouter secondary provider model is qwen/qwen3.8-27b:free."""
    s = Settings()
    assert s.secondary_ai_provider_name == "openrouter"
    assert s.effective_secondary_model == "qwen/qwen3.8-27b:free"


def test_no_secret_in_provider_diagnostics():
    """Verify provider health and error messages never leak API keys."""
    secret_key = "AIzaSySecretTestKeyNotForOutput99"
    provider = GeminiProvider(api_key=secret_key, model_name="models/gemini-3.8-flash")
    health = provider.get_health()

    assert secret_key not in health.model_name
    assert secret_key not in health.provider_name
    assert secret_key not in str(health.status)
    assert secret_key not in str(health)
