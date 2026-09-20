import pytest
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.embeddings import embedding_service
from backend.app.services.retrieval import retrieval_service


@pytest.mark.asyncio
async def test_strict_workspace_isolation():
    from backend.app.repositories.documents import document_repo

    # Create documents first to satisfy foreign key constraint
    doc_dsa = await document_repo.create(
        workspace_id="dsa",
        title="DSA Notes",
        filename="DSA_Notes.pdf",
        file_type="pdf",
        file_size=1024,
    )
    doc_os = await document_repo.create(
        workspace_id="os",
        title="OS Notes",
        filename="OS_Notes.pdf",
        file_type="pdf",
        file_size=1024,
    )

    # Insert a chunk into 'dsa' workspace
    dsa_text = "Red-Black Trees maintain balance through color rotation invariants."
    dsa_emb = await embedding_service.get_embedding(dsa_text)
    await chunk_repo.insert_chunks(
        [
            {
                "id": "chunk_dsa_1",
                "workspace_id": "dsa",
                "document_id": doc_dsa["id"],
                "chunk_index": 0,
                "page_number": 5,
                "text": dsa_text,
                "embedding": dsa_emb,
                "document_name": "DSA_Notes.pdf",
            }
        ]
    )

    # Insert a chunk into 'os' workspace
    os_text = "Demand paging causes thrashing when working set exceeds physical frames."
    os_emb = await embedding_service.get_embedding(os_text)
    await chunk_repo.insert_chunks(
        [
            {
                "id": "chunk_os_1",
                "workspace_id": "os",
                "document_id": doc_os["id"],
                "chunk_index": 0,
                "page_number": 12,
                "text": os_text,
                "embedding": os_emb,
                "document_name": "OS_Notes.pdf",
            }
        ]
    )

    # Search in 'os' workspace for a DSA topic
    chunks_os, is_grounded_os, _ = await retrieval_service.retrieve_relevant_chunks(
        workspace_id="os",
        query="Red-Black tree color rotation invariants",
    )
    # The 'dsa' chunk MUST NOT be returned from the 'os' workspace
    for c in chunks_os:
        assert c.workspace_id == "os"
        assert "Red-Black" not in c.text

    # Search in 'dsa' workspace for the DSA topic
    chunks_dsa, is_grounded_dsa, _ = await retrieval_service.retrieve_relevant_chunks(
        workspace_id="dsa",
        query="Red-Black tree color rotation invariants",
    )
    assert is_grounded_dsa is True
    assert len(chunks_dsa) >= 1
    assert "Red-Black" in chunks_dsa[0].text
    assert chunks_dsa[0].document_name == "DSA_Notes.pdf"
    assert chunks_dsa[0].page_number == 5
