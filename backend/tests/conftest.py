import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.repositories.workspaces import _memory_workspaces
from backend.app.repositories.documents import _memory_documents
from backend.app.repositories.chunks import _memory_chunks
from backend.app.repositories.tutor import _memory_conversations, _memory_messages


@pytest.fixture(autouse=True)
def reset_memory_store():
    """Resets memory state before each test."""
    _memory_documents.clear()
    _memory_chunks.clear()
    _memory_conversations.clear()
    _memory_messages.clear()
    yield


TEST_USER_ID = "usr_test_default"
TEST_USER_EMAIL = "tester@lumora.test"


def auth_headers_for_test_user() -> dict:
    """Authorization header for the default test user (for tests that build their own client)."""
    from backend.app.core.security import create_session_token

    return {"Authorization": f"Bearer {create_session_token(TEST_USER_ID)}"}


@pytest_asyncio.fixture(autouse=True)
async def ensure_test_workspaces(monkeypatch):
    """
    Every test runs as a signed-in test user who owns the test workspaces.

    - The test user exists in memory (and in the database when DATABASE_URL is set).
    - Workspaces created directly through the repository default to that owner, so tests that
      seed data without going through the API can still call the authenticated endpoints.
    """
    from backend.app.db.connection import get_db_pool
    from backend.app.repositories.users import _memory_users
    from backend.app.repositories.workspaces import WorkspaceRepository

    _memory_users[TEST_USER_ID] = {
        "id": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "name": "Test User",
        "password_hash": "unused",
        "created_at": None,
        "last_login_at": None,
    }
    for ws in _memory_workspaces.values():
        if not ws.get("owner_id"):
            ws["owner_id"] = TEST_USER_ID

    original_create = WorkspaceRepository.create

    async def create_with_test_owner(self, *args, owner_id=None, **kwargs):
        return await original_create(self, *args, owner_id=owner_id or TEST_USER_ID, **kwargs)

    monkeypatch.setattr(WorkspaceRepository, "create", create_with_test_owner)

    pool = await get_db_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash)
                    VALUES ($1, $2, 'Test User', 'unused')
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    TEST_USER_ID,
                    TEST_USER_EMAIL,
                )
                for ws_id, ws_name in [
                    ("ml", "Machine Learning Test"),
                    ("os", "Operating Systems Test"),
                    ("dsa", "Data Structures Test"),
                    ("crypto", "Cryptography Test"),
                ]:
                    await conn.execute(
                        """
                        INSERT INTO workspaces (id, name, goal, description, owner_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE SET owner_id = EXCLUDED.owner_id;
                        """,
                        ws_id,
                        ws_name,
                        f"Test workspace {ws_id}",
                        f"Test description {ws_id}",
                        TEST_USER_ID,
                    )
        except Exception:
            pass
    yield


@pytest_asyncio.fixture(autouse=True)
async def auto_close_db_pool():
    """Ensures database connection pool is cleanly closed inside the active test loop."""
    yield
    from backend.app.db.connection import close_db_pool
    await close_db_pool()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """API client authenticated as the test user."""
    from backend.app.core.security import create_session_token

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {create_session_token(TEST_USER_ID)}"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client


@pytest_asyncio.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """API client without credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
