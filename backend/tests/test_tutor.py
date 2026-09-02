import pytest
from httpx import AsyncClient
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.embeddings import embedding_service
from backend.app.services.tutor import TutorService
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_tutor_model_configurability():
    # Verify default configured generation model
    tutor_default = TutorService()
    assert tutor_default.model_name == settings.gemini_model

    # Verify custom model override
    tutor_custom = TutorService(model_name="gemini-3.5-flash")
    assert tutor_custom.model_name == "gemini-3.5-flash"


@pytest.mark.asyncio
async def test_ask_tutor_with_grounded_citations(async_client: AsyncClient):
    # Seed document chunk in 'dsa' workspace
    fact_text = "In directed cycle detection, a back-edge points to an ancestor currently on the recursion stack."
    fact_emb = await embedding_service.get_embedding(fact_text)
    await chunk_repo.insert_chunks(
        [
            {
                "id": "chunk_tutor_1",
                "workspace_id": "dsa",
                "document_id": "doc_tutor_1",
                "chunk_index": 0,
                "page_number": 42,
                "text": fact_text,
                "embedding": fact_emb,
                "document_name": "Graph_Algorithms.pdf",
            }
        ]
    )

    response = await async_client.post(
        "/api/v1/workspaces/dsa/tutor",
        json={"message": "How do we detect cycles in directed graphs with back edges?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] is not None
    assert data["message"]["role"] == "assistant"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document_name"] == "Graph_Algorithms.pdf"
    assert data["citations"][0]["page_or_slide"] == 42
    assert data["retrieval"]["grounded"] is True


@pytest.mark.asyncio
async def test_tutor_refusal_when_unsupported_by_sources(async_client: AsyncClient):
    # Query completely unrelated topic in an empty workspace
    response = await async_client.post(
        "/api/v1/workspaces/aws/tutor",
        json={"message": "What is the capital of ancient Mesopotamia in 2000 BCE?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "not contain enough information" in data["message"]["content"]
    assert len(data["citations"]) == 0
    assert data["retrieval"]["grounded"] is False
