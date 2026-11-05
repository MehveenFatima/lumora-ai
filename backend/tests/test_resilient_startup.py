"""The API must keep serving, and say why, while its database is unreachable (e.g. a paused project)."""
import asyncio
import time

import pytest

from backend.app.core.config import settings
from backend.app.db import connection
from backend.app.db.migrations_runner import apply_migrations, describe_db_error, migration_files


class _PoolerError(Exception):
    pass


def test_database_errors_are_described_without_details():
    assert describe_db_error(_PoolerError("Tenant or user not found")) == "project_not_found_or_paused"
    assert describe_db_error(_PoolerError('password authentication failed for user "x"')) == "authentication_failed"
    assert describe_db_error(ConnectionRefusedError("[Errno 111] Connection refused")) == "connection_refused"
    assert describe_db_error(OSError("[Errno -2] Name or service not known")) == "host_not_found"
    assert describe_db_error(asyncio.TimeoutError()) == "timeout"
    assert describe_db_error(ValueError("something else")) == "ValueError"


@pytest.fixture
def unreachable_database(monkeypatch):
    """Production settings with a configured database that just failed to connect."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)
    monkeypatch.setattr(settings, "database_url", "postgresql://user@db.invalid:5432/postgres")
    monkeypatch.setattr(connection, "_pool", None)
    monkeypatch.setattr(connection, "_last_failure", time.monotonic())
    monkeypatch.setattr(connection, "_last_error", "project_not_found_or_paused")


@pytest.mark.asyncio
async def test_health_stays_up_and_reports_the_outage(async_client, unreachable_database):
    res = await async_client.get("/api/v1/health")
    # Liveness: the process is fine, so the host must not restart or roll back the service
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "unavailable"
    assert body["database"]["error"] == "project_not_found_or_paused"


@pytest.mark.asyncio
async def test_scheduled_database_check_fails_during_an_outage(async_client, unreachable_database):
    res = await async_client.get("/api/v1/health?check_db=true")
    assert res.status_code == 503
    assert res.json()["database"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_data_requests_get_a_clear_503_during_an_outage(async_client, unreachable_database):
    res = await async_client.post(
        "/api/v1/auth/login", json={"email": "someone@example.com", "password": "a-password-123"}
    )
    assert res.status_code == 503
    assert "temporarily unavailable" in res.text


@pytest.mark.asyncio
async def test_reconnects_and_runs_setup_once_the_database_is_back(monkeypatch):
    calls = {"pool": 0, "ready": 0}

    async def fake_pool():
        calls["pool"] += 1
        return object() if calls["pool"] >= 3 else None

    async def on_ready():
        calls["ready"] += 1

    monkeypatch.setattr(connection, "get_db_pool", fake_pool)
    await asyncio.wait_for(connection.keep_connecting(on_ready, interval=0.01), timeout=2)
    assert calls == {"pool": 3, "ready": 1}


@pytest.mark.asyncio
async def test_migrations_are_idempotent():
    if not settings.database_url:
        pytest.skip("needs PostgreSQL")
    import asyncpg

    conn = await asyncpg.connect(settings.database_url)
    try:
        total, done = await apply_migrations(conn)
        assert total == len(migration_files())
        assert done == []  # the test database is already migrated; nothing runs twice
        total, done = await apply_migrations(conn)
        assert done == []
    finally:
        await conn.close()
