import pytest
import numpy as np
from backend.app.services.embeddings import embedding_service, l2_normalize


@pytest.mark.asyncio
async def test_embedding_generation_and_dimension():
    text = "Explain Dijkstra's shortest path algorithm using a priority queue."
    embedding = await embedding_service.get_embedding(text)
    assert isinstance(embedding, list)
    assert len(embedding) == 768
    # Verify vector is L2 normalized
    norm = np.linalg.norm(np.array(embedding, dtype=np.float32))
    assert pytest.approx(norm, 0.01) == 1.0


@pytest.mark.asyncio
async def test_query_embedding_dimension():
    query = "How does Bellman-Ford handle negative cycles?"
    embedding = await embedding_service.get_query_embedding(query)
    assert len(embedding) == 768
