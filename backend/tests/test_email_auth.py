"""
Email verification, password reset and account management.

Email delivery is replaced by an in-memory outbox, so these tests need no email provider.
"""
import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.routes import auth as auth_routes
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.repositories import auth_codes
from backend.app.services.email_service import EmailDeliveryError, email_service

PASSWORD = "Str0ngPassw0rd"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(autouse=True)
def clean_state():
    for limiter in (auth_routes.login_limiter, auth_routes.register_limiter,
                    auth_routes.code_request_limiter, auth_routes.code_verify_limiter):
        limiter._hits.clear()
    auth_codes._memory_codes.clear()
    yield


@pytest.fixture
def outbox(monkeypatch):
    """Turns email on and captures every code that would have been sent."""
    sent = []

    async def capture(to_email, name, code, purpose):
        sent.append({"to": to_email, "code": code, "purpose": purpose})

    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "noreply@lumora.test")
    monkeypatch.setattr(settings, "email_verification", "auto")
    monkeypatch.setattr(email_service, "send_code", capture)
    return sent


def _last_code(outbox, email, purpose):
    return [m for m in outbox if m["to"] == email and m["purpose"] == purpose][-1]["code"]


async def _age_codes():
    """Moves every stored code an hour into the past (memory store or PostgreSQL)."""
    from datetime import timedelta

    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE email_codes SET created_at = created_at - INTERVAL '2 hours'")
    for rec in auth_codes._memory_codes:
        rec["created_at"] -= timedelta(hours=2)


async def _register(client, email, password=PASSWORD):
    return await client.post("/api/v1/auth/register", json={"name": "Asha Rao", "email": email, "password": password})


@pytest.mark.asyncio
async def test_without_email_provider_signup_signs_in_directly():
    async with _client() as c:
        cfg = (await c.get("/api/v1/auth/config")).json()
        assert cfg == {"email_verification_required": False, "password_reset_available": False}
        res = await _register(c, _email("plain"))
        assert res.status_code == 201
        assert res.json()["verification_required"] is False
        assert (await c.get("/api/v1/auth/me")).status_code == 200
        forgot = await c.post("/api/v1/auth/forgot-password", json={"email": "someone@example.com"})
        assert forgot.status_code == 503


@pytest.mark.asyncio
async def test_signup_requires_the_emailed_code(outbox):
    email = _email("verify")
    async with _client() as c:
        res = await _register(c, email)
        body = res.json()
        assert res.status_code == 201 and body["verification_required"] is True and body["email_sent"] is True
        assert body["access_token"] is None
        assert "lumora_session" not in res.headers.get("set-cookie", "")
        assert (await c.get("/api/v1/auth/me")).status_code == 401

        code = _last_code(outbox, email, "verify_email")
        assert re.fullmatch(r"\d{6}", code)

        # Signing in before verifying sends a fresh code and says why
        login = await c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 403 and login.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"

        wrong = "000000" if code != "000000" else "111111"
        bad = await c.post("/api/v1/auth/verify-email", json={"email": email, "code": wrong})
        assert bad.status_code == 400

        ok = await c.post("/api/v1/auth/verify-email", json={"email": email, "code": code})
        assert ok.status_code == 200
        assert (await c.get("/api/v1/auth/me")).json()["email"] == email

        # Codes are single-use
        again = await c.post("/api/v1/auth/verify-email", json={"email": email, "code": code})
        assert again.status_code == 400

        notes = (await c.get("/api/v1/notifications")).json()
        assert any(n["type"] == "welcome" for n in notes["items"])


@pytest.mark.asyncio
async def test_code_locks_after_five_wrong_attempts(outbox):
    email = _email("lock")
    async with _client() as c:
        await _register(c, email)
        code = _last_code(outbox, email, "verify_email")
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(auth_codes.MAX_ATTEMPTS):
            assert (await c.post("/api/v1/auth/verify-email", json={"email": email, "code": wrong})).status_code == 400
        # Even the right code no longer works; a new one must be requested
        assert (await c.post("/api/v1/auth/verify-email", json={"email": email, "code": code})).status_code == 400


@pytest.mark.asyncio
async def test_resend_is_rate_limited_per_account(outbox, monkeypatch):
    email = _email("resend")
    async with _client() as c:
        await _register(c, email)
        first = len(outbox)
        res = await c.post("/api/v1/auth/resend-verification", json={"email": email})
        assert res.status_code == 202
        assert len(outbox) == first  # within the 60 s cooldown the earlier code is still valid

        # After the cooldown a new code replaces the old one
        await _age_codes()
        await c.post("/api/v1/auth/resend-verification", json={"email": email})
        assert len(outbox) == first + 1
        old, new = outbox[first - 1]["code"], outbox[-1]["code"]
        if old != new:
            assert (await c.post("/api/v1/auth/verify-email", json={"email": email, "code": old})).status_code == 400
        assert (await c.post("/api/v1/auth/verify-email", json={"email": email, "code": new})).status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_does_not_reveal_accounts(outbox):
    async with _client() as c:
        unknown = await c.post("/api/v1/auth/forgot-password", json={"email": _email("nobody")})
        assert unknown.status_code == 202
        assert outbox == []

        email = _email("known")
        await _register(c, email)
        await c.post("/api/v1/auth/verify-email", json={"email": email, "code": _last_code(outbox, email, "verify_email")})
        known = await c.post("/api/v1/auth/forgot-password", json={"email": email})
        assert known.status_code == 202
        assert known.json()["message"] == unknown.json()["message"]
        assert _last_code(outbox, email, "reset_password")


@pytest.mark.asyncio
async def test_password_reset_signs_out_old_sessions(outbox):
    email = _email("reset")
    async with _client() as old_browser, _client() as new_browser:
        await _register(old_browser, email)
        await old_browser.post("/api/v1/auth/verify-email", json={"email": email, "code": _last_code(outbox, email, "verify_email")})
        assert (await old_browser.get("/api/v1/auth/me")).status_code == 200

        await new_browser.post("/api/v1/auth/forgot-password", json={"email": email})
        code = _last_code(outbox, email, "reset_password")
        weak = await new_browser.post("/api/v1/auth/reset-password", json={"email": email, "code": code, "new_password": "short"})
        assert weak.status_code == 422
        reset = await new_browser.post(
            "/api/v1/auth/reset-password", json={"email": email, "code": code, "new_password": "N3wPassword99"}
        )
        assert reset.status_code == 200
        assert (await new_browser.get("/api/v1/auth/me")).status_code == 200
        assert (await old_browser.get("/api/v1/auth/me")).status_code == 401  # old session ended

        assert (await new_browser.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})).status_code == 401
        assert (await new_browser.post("/api/v1/auth/login", json={"email": email, "password": "N3wPassword99"})).status_code == 200


@pytest.mark.asyncio
async def test_failed_delivery_is_reported_and_retryable(outbox, monkeypatch):
    async def broken(*args, **kwargs):
        raise EmailDeliveryError("provider down")

    monkeypatch.setattr(email_service, "send_code", broken)
    email = _email("down")
    async with _client() as c:
        res = await _register(c, email)
        assert res.status_code == 201 and res.json()["email_sent"] is False
        assert auth_codes._memory_codes == []  # the unsent code was withdrawn, so resend isn't blocked
        resend = await c.post("/api/v1/auth/resend-verification", json={"email": email})
        assert resend.status_code == 503


@pytest.mark.asyncio
async def test_change_password_profile_and_delete_account():
    async with _client() as c, _client() as other_device:
        email = _email("acct")
        await _register(c, email)
        await other_device.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})

        renamed = await c.patch("/api/v1/auth/me", json={"name": "Asha R"})
        assert renamed.status_code == 200 and renamed.json()["name"] == "Asha R"

        wrong = await c.post("/api/v1/auth/change-password", json={"current_password": "nope12345", "new_password": "An0therPass1"})
        assert wrong.status_code == 400
        same = await c.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD})
        assert same.status_code == 400
        ok = await c.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "An0therPass1"})
        assert ok.status_code == 200
        assert (await c.get("/api/v1/auth/me")).status_code == 200  # this browser got a new session
        assert (await other_device.get("/api/v1/auth/me")).status_code == 401

        ws = await c.post("/api/v1/workspaces", json={"name": "To delete", "goal": "g", "level": "beginner"})
        assert ws.status_code in (200, 201)

        bad = await c.request("DELETE", "/api/v1/auth/me", json={"password": "wrong-pass1"})
        assert bad.status_code == 400
        gone = await c.request("DELETE", "/api/v1/auth/me", json={"password": "An0therPass1"})
        assert gone.status_code == 204
        assert (await c.get("/api/v1/auth/me")).status_code == 401
        assert (await c.post("/api/v1/auth/login", json={"email": email, "password": "An0therPass1"})).status_code == 401
