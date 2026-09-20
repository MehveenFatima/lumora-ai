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
    import uuid
    from backend.app.repositories.documents import document_repo

    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Grounded Citation Test WS", "goal": "Testing citations", "level": "intermediate"},
    )
    ws_id = ws_res.json()["id"]
    try:
        doc = await document_repo.create(
            workspace_id=ws_id,
            title="Graph Algorithms",
            filename="Graph_Algorithms.pdf",
            file_type="pdf",
            file_size=2048,
            page_count=50,
            status="ready",
        )
        doc_id = str(doc["id"])
        fact_text = "In directed cycle detection, a back-edge points to an ancestor currently on the recursion stack."
        fact_emb = await embedding_service.get_embedding(fact_text)
        await chunk_repo.insert_chunks(
            [
                {
                    "id": str(uuid.uuid4()),
                    "workspace_id": ws_id,
                    "document_id": doc_id,
                    "chunk_index": 0,
                    "page_number": 42,
                    "text": fact_text,
                    "embedding": fact_emb,
                    "document_name": "Graph_Algorithms.pdf",
                }
            ]
        )

        response = await async_client.post(
            f"/api/v1/workspaces/{ws_id}/tutor",
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
    finally:
        await async_client.delete(f"/api/v1/workspaces/{ws_id}")


@pytest.mark.asyncio
async def test_tutor_refusal_when_unsupported_by_sources(async_client: AsyncClient):
    # Query completely unrelated topic in an empty workspace
    ws_res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Empty Refusal Test WS", "goal": "Refusal testing", "level": "beginner"},
    )
    ws_id = ws_res.json()["id"]
    try:
        response = await async_client.post(
            f"/api/v1/workspaces/{ws_id}/tutor",
            json={"message": "What is the capital of ancient Mesopotamia in 2000 BCE?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "not contain enough information" in data["message"]["content"]
    finally:
        await async_client.delete(f"/api/v1/workspaces/{ws_id}")
    assert len(data["citations"]) == 0
    assert data["retrieval"]["grounded"] is False
