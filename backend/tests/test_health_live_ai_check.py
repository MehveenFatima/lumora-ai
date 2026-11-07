"""The live AI check runs only for the scheduler (cron secret) and never exposes keys."""
import pytest

from backend.app.ai.gateway import ai_gateway
from backend.app.core.config import settings


class _FakeProvider:
    model_name = "fake-model"

    def __init__(self, fail=False):
        self.fail = fail

    def is_configured(self):
        return True

    async def generate_text(self, request):
        if self.fail:
            raise RuntimeError("429 quota exceeded for key AIzaSyA1234567890abcdefghijklmnopqrstuv")

        class R:
            model = "fake-model"

        return R()


@pytest.mark.asyncio
async def test_live_ai_check_needs_the_cron_secret(async_client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value-for-cron")
    monkeypatch.setattr(ai_gateway, "providers", {"gemini": _FakeProvider(), "groq": _FakeProvider(fail=True)})
    monkeypatch.setattr(ai_gateway, "get_readiness_report", lambda: {"providers": {}})

    anon = (await async_client.get("/api/v1/health?check_ai=true")).json()
    assert "live_check" not in anon["ai"]

    res = (await async_client.get(
        "/api/v1/health?check_ai=true", headers={"X-Cron-Secret": "s3cret-value-for-cron"}
    )).json()
    live = res["ai"]["live_check"]
    assert live["gemini"]["ok"] is True
    assert live["groq"]["ok"] is False and "429" in live["groq"]["error"]
    assert "AIzaSyA1234567890abcdefghijklmnopqrstuv" not in str(res)
