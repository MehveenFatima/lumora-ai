"""
Accounts, sessions and per-user data isolation.
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.routes.auth import login_limiter, register_limiter
from backend.app.core.security import create_session_token, hash_password, verify_password
from backend.app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: AsyncClient, email: str, password: str = "Str0ngPassw0rd", name: str = "Learner"):
    return await client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": password})


@pytest.fixture(autouse=True)
def reset_rate_limits():
    login_limiter._hits.clear()
    register_limiter._hits.clear()
    yield
    login_limiter._hits.clear()
    register_limiter._hits.clear()


def test_password_hashing_round_trip():
    encoded = hash_password("correct horse 1")
    assert encoded.startswith("pbkdf2_sha256$600000$")
    assert verify_password("correct horse 1", encoded)
    assert not verify_password("wrong horse 1", encoded)
    assert hash_password("same") != hash_password("same")  # salted


@pytest.mark.asyncio
async def test_register_sets_session_cookie_and_me_works():
    async with _client() as client:
        email = _email("reg")
        res = await _register(client, email, name="Asha")
        assert res.status_code == 201
        body = res.json()
        assert body["user"]["email"] == email
        assert "password_hash" not in body["user"]
        set_cookie = res.headers.get("set-cookie", "")
        assert "lumora_session=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=lax" in set_cookie

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Asha"


@pytest.mark.asyncio
async def test_register_validation_and_duplicates():
    async with _client() as client:
        assert (await _register(client, "not-an-email")).status_code == 422
        assert (await _register(client, _email("weak"), password="short1")).status_code == 422
        assert (await _register(client, _email("weak"), password="lettersonly")).status_code == 422

        email = _email("dup")
        assert (await _register(client, email)).status_code == 201
        dup = await _register(client, email.upper())
        assert dup.status_code == 409


@pytest.mark.asyncio
async def test_login_logout_flow():
    email = _email("login")
    async with _client() as client:
        await _register(client, email, password="Passw0rd123")

    async with _client() as client:
        bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong12345"})
        assert bad.status_code == 401
        unknown = await client.post("/api/v1/auth/login", json={"email": _email("nobody"), "password": "Passw0rd123"})
        assert unknown.status_code == 401
        assert bad.json()["detail"] == unknown.json()["detail"]  # no account enumeration

        ok = await client.post("/api/v1/auth/login", json={"email": email.upper(), "password": "Passw0rd123"})
        assert ok.status_code == 200
        assert (await client.get("/api/v1/auth/me")).status_code == 200

        out = await client.post("/api/v1/auth/logout")
        assert out.status_code == 204
        client.cookies.clear()
        assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit():
    email = _email("rl")
    async with _client() as client:
        await _register(client, email)
        codes = [
            (await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong12345"})).status_code
            for _ in range(11)
        ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


@pytest.mark.asyncio
async def test_protected_routes_require_authentication():
    async with _client() as client:
        for method, path in [
            ("GET", "/api/v1/workspaces"),
            ("POST", "/api/v1/workspaces"),
            ("GET", "/api/v1/workspaces/ml"),
            ("GET", "/api/v1/workspaces/ml/documents"),
            ("POST", "/api/v1/workspaces/ml/tutor"),
            ("POST", "/api/v1/workspaces/ml/quizzes"),
            ("GET", "/api/v1/workspaces/ml/learner-profile"),
            ("GET", "/api/v1/workspaces/ml/flashcards"),
            ("GET", "/api/v1/workspaces/ml/study-plan"),
            ("GET", "/api/v1/activities"),
        ]:
            res = await client.request(method, path, json={} if method == "POST" else None)
            assert res.status_code == 401, f"{method} {path} returned {res.status_code}"
        assert (await client.get("/api/v1/health")).status_code == 200


@pytest.mark.asyncio
async def test_invalid_or_forged_tokens_are_rejected():
    async with _client() as client:
        res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert res.status_code == 401
        # A validly signed token for a user that does not exist
        forged = create_session_token("usr_does_not_exist")
        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_users_cannot_see_each_others_data():
    async with _client() as alice, _client() as bob:
        await _register(alice, _email("alice"), name="Alice")
        await _register(bob, _email("bob"), name="Bob")

        ws = await alice.post("/api/v1/workspaces", json={"name": "Alice OS", "goal": "Pass OS", "level": "beginner"})
        assert ws.status_code == 201
        ws_id = ws.json()["id"]

        up = await alice.post(
            f"/api/v1/workspaces/{ws_id}/documents",
            files={"file": ("notes.txt", b"Paging maps virtual pages to physical frames using page tables.", "text/plain")},
        )
        assert up.status_code in (200, 201, 202)
        doc_id = up.json()["id"]

        # Alice sees her workspace; Bob does not
        assert [w["id"] for w in (await alice.get("/api/v1/workspaces")).json()["workspaces"]] == [ws_id]
        assert (await bob.get("/api/v1/workspaces")).json()["workspaces"] == []

        # Every workspace- and document-scoped route answers 404 for Bob
        for method, path in [
            ("GET", f"/api/v1/workspaces/{ws_id}"),
            ("GET", f"/api/v1/workspaces/{ws_id}/documents"),
            ("GET", f"/api/v1/workspaces/{ws_id}/tutor/history"),
            ("GET", f"/api/v1/workspaces/{ws_id}/learner-profile"),
            ("GET", f"/api/v1/workspaces/{ws_id}/flashcards"),
            ("GET", f"/api/v1/workspaces/{ws_id}/activity"),
            ("GET", f"/api/v1/documents/{doc_id}"),
            ("GET", f"/api/v1/documents/{doc_id}/download"),
            ("DELETE", f"/api/v1/documents/{doc_id}"),
            ("DELETE", f"/api/v1/workspaces/{ws_id}"),
        ]:
            res = await bob.request(method, path)
            assert res.status_code == 404, f"Bob got {res.status_code} for {method} {path}"

        tutor = await bob.post(f"/api/v1/workspaces/{ws_id}/tutor", json={"message": "What is paging?"})
        assert tutor.status_code == 404

        # Global activity feed only contains the caller's own workspaces
        bob_acts = (await bob.get("/api/v1/activities")).json()["activities"]
        assert all(a["workspace_id"] != ws_id for a in bob_acts)

        # Alice's data is intact after Bob's attempts
        assert (await alice.get(f"/api/v1/documents/{doc_id}")).status_code == 200
        assert (await alice.get(f"/api/v1/workspaces/{ws_id}")).status_code == 200


@pytest.mark.asyncio
async def test_client_cannot_choose_workspace_id():
    async with _client() as client:
        await _register(client, _email("ids"))
        res = await client.post(
            "/api/v1/workspaces", json={"id": "ml", "name": "Hijack", "goal": "x", "level": "beginner"}
        )
        assert res.status_code == 201
        assert res.json()["id"] != "ml"
