"""
Embedding safety: batched Gemini calls, no silent fallback to offline vectors,
and queries embedded in the same vector space as the chunks they are compared with.
"""
import math
import uuid
from unittest.mock import patch

import pytest

from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.services.embeddings import (
    OFFLINE_EMBEDDING_TAG,
    EmbeddingUnavailableError,
    embedding_service,
    generate_deterministic_mock_embedding,
)
from backend.app.services.retrieval import retrieval_service


async def _no_sleep(*_args, **_kwargs):
    return None


@pytest.fixture
def gemini_configured():
    original_key, original_init = embedding_service.api_key, embedding_service._gemini_client_initialized
    embedding_service.api_key = "test-placeholder-key"
    embedding_service._gemini_client_initialized = True
    embedding_service._cooldown_until = None
    yield
    embedding_service.api_key = original_key
    embedding_service._gemini_client_initialized = original_init
    embedding_service._cooldown_until = None


@pytest.mark.asyncio
async def test_offline_mode_tags_vectors_and_is_deterministic():
    vectors, tag = await embedding_service.embed_documents(["paging and page tables", "process scheduling"])
    assert tag == OFFLINE_EMBEDDING_TAG
    assert len(vectors) == 2 and all(len(v) == 768 for v in vectors)
    again = await embedding_service.embed_query_for("paging and page tables", OFFLINE_EMBEDDING_TAG)
    assert again == generate_deterministic_mock_embedding("paging and page tables", 768)


@pytest.mark.asyncio
async def test_gemini_embeddings_are_batched_and_normalized(gemini_configured):
    calls = []

    def fake_embed_content(model, content, task_type, output_dimensionality):
        calls.append(len(content))
        return {"embedding": [[3.0] + [4.0] + [0.0] * 3070 for _ in content]}

    with patch("google.generativeai.embed_content", side_effect=fake_embed_content):
        vectors, tag = await embedding_service.embed_documents([f"chunk {i}" for i in range(250)])

    assert tag == "gemini-embedding-001"
    assert calls == [100, 100, 50]
    assert len(vectors) == 250 and len(vectors[0]) == 768
    assert math.isclose(sum(x * x for x in vectors[0]), 1.0, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_gemini_failure_raises_instead_of_storing_offline_vectors(gemini_configured):
    with patch("google.generativeai.embed_content", side_effect=Exception("HTTP 429 quota exceeded")), patch(
        "backend.app.services.embeddings.asyncio.sleep", side_effect=_no_sleep
    ):
        with pytest.raises(EmbeddingUnavailableError):
            await embedding_service.embed_documents(["some text"])


@pytest.mark.asyncio
async def test_query_for_unavailable_space_returns_none(gemini_configured):
    with patch("google.generativeai.embed_content", side_effect=Exception("HTTP 429 quota exceeded")):
        assert await embedding_service.embed_query_for("what is paging", "gemini-embedding-001") is None
    # An unknown model space can never be produced
    assert await embedding_service.embed_query_for("what is paging", "some-other-model") is None


@pytest.mark.asyncio
async def test_offline_seeded_chunks_still_retrieved_when_gemini_is_configured(gemini_configured):
    """Offline-embedded chunks are searched with offline query vectors even when a Gemini key exists."""
    from backend.app.repositories.workspaces import workspace_repo

    ws_id = f"ws_embed_{uuid.uuid4().hex[:8]}"
    await workspace_repo.create(workspace_id=ws_id, name="Embedding test", goal="Test")
    doc = await document_repo.create(
        workspace_id=ws_id, title="OS notes", filename="os_notes.txt", file_type="txt",
        file_size=100, page_count=1, status="ready",
    )
    text = "Virtual memory uses page tables to translate virtual addresses into physical frame numbers."
    await chunk_repo.insert_chunks([{
        "id": str(uuid.uuid4()), "workspace_id": ws_id, "document_id": str(doc["id"]),
        "document_name": "os_notes.txt", "chunk_index": 0, "page_number": 1, "heading": "Virtual memory",
        "text": text, "token_count": 20,
        "embedding": generate_deterministic_mock_embedding(text, 768),
        "metadata": {"embedding_model": OFFLINE_EMBEDDING_TAG},
    }])

    def gemini_must_not_be_used(*_a, **_k):
        raise AssertionError("Gemini should not be called for an offline-embedded workspace")

    with patch("google.generativeai.embed_content", side_effect=gemini_must_not_be_used):
        results = await retrieval_service._vector_search(ws_id, "How do page tables translate virtual addresses?", top_k=3)
    assert results and results[0]["text"] == text


@pytest.mark.asyncio
async def test_upload_returns_503_and_leaves_no_record_when_embeddings_fail(async_client, gemini_configured):
    with patch("google.generativeai.embed_content", side_effect=Exception("HTTP 503 unavailable")), patch(
        "backend.app.services.embeddings.asyncio.sleep", side_effect=_no_sleep
    ):
        res = await async_client.post(
            "/api/v1/workspaces/ml/documents",
            files={"file": ("notes.txt", b"Gradient descent minimizes a loss function step by step.", "text/plain")},
        )
    assert res.status_code == 503
    docs = (await async_client.get("/api/v1/workspaces/ml/documents")).json()["documents"]
    assert all(d["filename"] != "notes.txt" or d["status"] == "ready" for d in docs)


@pytest.mark.asyncio
async def test_empty_document_is_rejected_cleanly(async_client):
    res = await async_client.post(
        "/api/v1/workspaces/ml/documents",
        files={"file": ("empty.txt", b"   \n  ", "text/plain")},
    )
    assert res.status_code in (400, 422)
