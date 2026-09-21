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


@pytest_asyncio.fixture(autouse=True)
async def ensure_test_workspaces():
    """Ensures test workspaces exist in DB if DB pool is active to satisfy foreign keys."""
    from backend.app.db.connection import get_db_pool
    pool = await get_db_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                for ws_id, ws_name in [
                    ("ml", "Machine Learning Test"),
                    ("os", "Operating Systems Test"),
                    ("dsa", "Data Structures Test"),
                    ("crypto", "Cryptography Test"),
                ]:
                    await conn.execute(
                        """
                        INSERT INTO workspaces (id, name, goal, description, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        ON CONFLICT (id) DO NOTHING;
                        """,
                        ws_id,
                        ws_name,
                        f"Test workspace {ws_id}",
                        f"Test description {ws_id}",
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
