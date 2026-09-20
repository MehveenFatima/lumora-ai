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
