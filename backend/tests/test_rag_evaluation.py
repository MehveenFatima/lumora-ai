import pytest
from httpx import AsyncClient
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.embeddings import embedding_service
from backend.app.services.retrieval import retrieval_service


@pytest.mark.asyncio
async def test_rag_evaluation_known_facts(async_client: AsyncClient):
    """
    RAG Evaluation Suite:
    Tests known ground truth retrieval, workspace isolation, citation correctness,
    and out-of-domain refusal.
    """
    # 1. Setup Ground Truth Document in Workspace 'ml'
    transformer_fact = (
        "The self-attention mechanism computes attention weights as Softmax((Q * K^T) / sqrt(d_k)) * V, "
        "enabling tokens to attend to all positions in parallel."
    )
    transformer_emb = await embedding_service.get_embedding(transformer_fact)
    await chunk_repo.insert_chunks(
        [
            {
                "id": "ml_chunk_attention",
                "workspace_id": "ml",
                "document_id": "doc_attention_is_all_you_need",
                "chunk_index": 3,
                "page_number": 4,
                "text": transformer_fact,
                "embedding": transformer_emb,
                "document_name": "Attention_Is_All_You_Need.pdf",
            }
        ]
    )

    # 2. Setup Ground Truth Document in Workspace 'os'
    virtual_memory_fact = (
        "Translation Lookaside Buffer (TLB) is a fast associative hardware cache storing virtual-to-physical "
        "page table mappings to reduce memory access latency."
    )
    vm_emb = await embedding_service.get_embedding(virtual_memory_fact)
    await chunk_repo.insert_chunks(
        [
            {
                "id": "os_chunk_tlb",
                "workspace_id": "os",
                "document_id": "doc_os_virtual_memory",
                "chunk_index": 7,
                "page_number": 19,
                "text": virtual_memory_fact,
                "embedding": vm_emb,
                "document_name": "Operating_Systems_Three_Easy_Pieces.pdf",
            }
        ]
    )

    # Test 1: Verify correct relevant chunk is retrieved for known question in 'ml'
    chunks, is_grounded, _ = await retrieval_service.retrieve_relevant_chunks(
        workspace_id="ml",
        query="What formula calculates the scaled dot-product self-attention weights?",
    )
    assert is_grounded is True
    assert len(chunks) >= 1
    assert "Softmax" in chunks[0].text
    assert chunks[0].document_name == "Attention_Is_All_You_Need.pdf"
    assert chunks[0].page_number == 4

    # Test 2: Verify workspace filtering prevents cross-domain retrieval
    chunks_in_os, is_grounded_in_os, _ = await retrieval_service.retrieve_relevant_chunks(
        workspace_id="os",
        query="What formula calculates the scaled dot-product self-attention weights?",
    )
    # The 'ml' document MUST NOT appear in the 'os' workspace retrieval
    for c in chunks_in_os:
        assert c.document_name != "Attention_Is_All_You_Need.pdf"

    # Test 3: Verify end-to-end Tutor response and citation metadata in 'os'
    res_os = await async_client.post(
        "/api/v1/workspaces/os/tutor",
        json={"message": "What is the purpose of the Translation Lookaside Buffer (TLB)?"},
    )
    assert res_os.status_code == 200
    os_data = res_os.json()
    assert os_data["retrieval"]["grounded"] is True
    assert len(os_data["citations"]) >= 1
    assert os_data["citations"][0]["document_name"] == "Operating_Systems_Three_Easy_Pieces.pdf"
    assert os_data["citations"][0]["page_or_slide"] == 19

    # Test 4: Verify refusal when asking an unsupported fact
    res_unsupported = await async_client.post(
        "/api/v1/workspaces/ml/tutor",
        json={"message": "How do you configure BGP route reflectors on Cisco IOS XE routers?"},
    )
    assert res_unsupported.status_code == 200
    unsupported_data = res_unsupported.json()
    assert "not contain enough information" in unsupported_data["message"]["content"]
    assert unsupported_data["retrieval"]["grounded"] is False
    assert len(unsupported_data["citations"]) == 0
