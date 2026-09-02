import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.repositories.workspaces import _memory_workspaces
from backend.app.repositories.documents import _memory_documents
from backend.app.repositories.chunks import _memory_chunks
from backend.app.repositories.tutor import _memory_conversations, _memory_messages


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_memory_store():
    """Resets memory state before each test."""
    _memory_documents.clear()
    _memory_chunks.clear()
    _memory_conversations.clear()
    _memory_messages.clear()
    yield


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
