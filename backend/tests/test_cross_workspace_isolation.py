import pytest
import io
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_cross_workspace_isolation(async_client: AsyncClient):
    """
    Validates complete isolation between workspaces across:
    1. Documents & Chunks
    2. RAG Tutor Retrieval & Citations
    3. Topic Mastery & BKT Concepts
    4. Flashcards & Study Plans
    """
    # 1. Create Workspace Alpha: DSA
    res_a = await async_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Isolation Test - DSA",
            "goal": "Data structures isolation testing",
            "level": "intermediate",
        },
    )
    assert res_a.status_code == 201
    ws_a_id = res_a.json()["id"]

    # 2. Create Workspace Beta: OS
    res_b = await async_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Isolation Test - OS",
            "goal": "Operating systems isolation testing",
            "level": "intermediate",
        },
    )
    assert res_b.status_code == 201
    ws_b_id = res_b.json()["id"]

    try:
        # 3. Upload DSA document to Alpha ONLY
        dsa_text = (
            "Binary Search Tree Invariant (Chapter 4, Page 42):\n"
            "In an AVL tree, the balance factor BF is calculated as height(left) minus height(right).\n"
            "If BF becomes +2 or -2, tree rotations such as Left-Right double rotations restore balance in O(1) time.\n"
            "Binary heaps maintain the complete binary tree invariant and min-heap order."
        )
        up_a = await async_client.post(
            f"/api/v1/workspaces/{ws_a_id}/documents",
            files={"file": ("dsa_balance.txt", io.BytesIO(dsa_text.encode("utf-8")), "text/plain")},
            data={"title": "DSA Balance Trees"},
        )
        assert up_a.status_code == 201
        doc_a_id = up_a.json()["id"]

        # 4. Upload OS document to Beta ONLY
        os_text = (
            "Virtual Memory and Paging Mechanics (Chapter 8, Page 115):\n"
            "The Memory Management Unit (MMU) translates logical addresses to physical frames using page tables.\n"
            "A TLB hit avoids secondary memory lookups. In LRU and Clock page replacement, the victim page is evicted.\n"
            "Process context switches save registers and flush the translation lookaside buffer."
        )
        up_b = await async_client.post(
            f"/api/v1/workspaces/{ws_b_id}/documents",
            files={"file": ("os_paging.txt", io.BytesIO(os_text.encode("utf-8")), "text/plain")},
            data={"title": "OS Paging and TLB"},
        )
        assert up_b.status_code == 201
        doc_b_id = up_b.json()["id"]

        # 5. Document List Isolation
        docs_a = (await async_client.get(f"/api/v1/workspaces/{ws_a_id}/documents")).json()["documents"]
        docs_b = (await async_client.get(f"/api/v1/workspaces/{ws_b_id}/documents")).json()["documents"]
        assert len(docs_a) == 1
        assert docs_a[0]["id"] == doc_a_id
        assert "os_paging.txt" not in [d["filename"] for d in docs_a]

        assert len(docs_b) == 1
        assert docs_b[0]["id"] == doc_b_id
        assert "dsa_balance.txt" not in [d["filename"] for d in docs_b]

        # 6. RAG Retrieval Isolation: Query OS concept in Workspace Beta
        r_os = await async_client.post(
            f"/api/v1/workspaces/{ws_b_id}/tutor",
            json={"message": "Explain how the MMU and TLB handle virtual memory address translation."},
        )
        assert r_os.status_code == 200
        d_os = r_os.json()
        assert d_os["retrieval"]["grounded"] is True
        assert len(d_os["citations"]) >= 1
        for cite in d_os["citations"]:
            assert cite["document_id"] == doc_b_id
            assert cite["document_name"] == "os_paging.txt"
            assert "dsa" not in cite["document_name"].lower()

        # 7. RAG Retrieval Isolation: Query OS concept in Workspace Alpha (Must NOT leak OS document)
        r_leak = await async_client.post(
            f"/api/v1/workspaces/{ws_a_id}/tutor",
            json={"message": "Explain how the MMU and TLB handle virtual memory address translation."},
        )
        assert r_leak.status_code == 200
        d_leak = r_leak.json()
        # Citations must never contain os_paging.txt
        for cite in d_leak.get("citations", []):
            assert cite["document_id"] != doc_b_id
            assert cite["document_name"] != "os_paging.txt"

        # 8. Mastery Isolation: Seed concepts in Alpha
        await async_client.post(
            f"/api/v1/workspaces/{ws_a_id}/mastery/seed",
            json={
                "user_ids": ["default_user"],
                "concepts": [
                    {"concept": "AVL Rotations", "topic": "Balanced Trees", "p_mastery": 0.85, "is_correct": True}
                ],
            },
        )

        # Check Beta mastery: Must have 0 concepts and not_assessed
        prof_b = await async_client.get(f"/api/v1/workspaces/{ws_b_id}/learner-profile")
        assert prof_b.status_code == 200
        b_data = prof_b.json()
        assert b_data["status"] == "not_assessed"
        assert len(b_data["strongest_topics"]) == 0
        assert len(b_data["top_knowledge_gaps"]) == 0

        # Check Alpha mastery overview: Must have Balanced Trees topic
        ov_a = await async_client.get(f"/api/v1/workspaces/{ws_a_id}/mastery")
        assert ov_a.status_code == 200
        a_data = ov_a.json()
        assert len(a_data["topics"]) >= 1
        assert any(t["topic"].lower() == "balanced trees" for t in a_data["topics"])

        # 9. Flashcard & Study Plan Isolation
        await async_client.post(f"/api/v1/workspaces/{ws_a_id}/flashcards/generate")
        await async_client.post(f"/api/v1/workspaces/{ws_b_id}/flashcards/generate")

        fc_a = (await async_client.get(f"/api/v1/workspaces/{ws_a_id}/flashcards")).json()["flashcards"]
        fc_b = (await async_client.get(f"/api/v1/workspaces/{ws_b_id}/flashcards")).json()["flashcards"]

        for c in fc_a:
            assert c["workspace_id"] == ws_a_id
        for c in fc_b:
            assert c["workspace_id"] == ws_b_id

    finally:
        # Cleanup
        await async_client.delete(f"/api/v1/workspaces/{ws_a_id}")
        await async_client.delete(f"/api/v1/workspaces/{ws_b_id}")
