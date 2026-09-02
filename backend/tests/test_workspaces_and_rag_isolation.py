import pytest
import io
from httpx import AsyncClient
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo


@pytest.mark.asyncio
async def test_workspace_crud_and_lifecycle(async_client: AsyncClient):
    # 1. Create a brand new workspace
    create_payload = {
        "name": "Distributed Systems Track",
        "goal": "Prepare for distributed systems design interviews",
        "level": "advanced",
        "target_date": "2026-11-30",
        "daily_target_minutes": 60,
        "description": "Consensus, Paxos, Raft, and distributed hash tables.",
        "icon_name": "Network",
    }
    create_res = await async_client.post("/api/v1/workspaces", json=create_payload)
    assert create_res.status_code == 201
    created_ws = create_res.json()
    ws_id = created_ws["id"]
    assert created_ws["name"] == "Distributed Systems Track"
    assert created_ws["document_count"] == 0

    # 2. Get by ID
    get_res = await async_client.get(f"/api/v1/workspaces/{ws_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ws_id

    # 3. List all workspaces includes the newly created one
    list_res = await async_client.get("/api/v1/workspaces")
    assert list_res.status_code == 200
    ws_ids = [w["id"] for w in list_res.json()["workspaces"]]
    assert ws_id in ws_ids

    # 4. Clean up workspace
    del_res = await async_client.delete(f"/api/v1/workspaces/{ws_id}")
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_real_rag_ingestion_retrieval_and_cross_workspace_isolation(async_client: AsyncClient):
    # Setup Workspace A: "RAG Test Workspace"
    ws_a_res = await async_client.post(
        "/api/v1/workspaces",
        json={
            "name": "RAG Test Workspace",
            "goal": "Verify isolated document retrieval and citations",
            "level": "intermediate",
        },
    )
    assert ws_a_res.status_code == 201
    ws_a_id = ws_a_res.json()["id"]

    # Setup Workspace B: "Empty Isolation Workspace"
    ws_b_res = await async_client.post(
        "/api/v1/workspaces",
        json={
            "name": "Empty Isolation Workspace",
            "goal": "Ensure 0 data leakage from other workspaces",
            "level": "beginner",
        },
    )
    assert ws_b_res.status_code == 201
    ws_b_id = ws_b_res.json()["id"]

    # Upload unique learning document ONLY to Workspace A
    unique_doc_content = (
        "Raft Consensus Protocol Specification (Page 1):\n"
        "In the Raft consensus algorithm, a leader maintains term numbers and heartbeats.\n"
        "When a follower detects a leader election timeout, it transitions to candidate state,\n"
        "increments the currentTerm counter, votes for itself, and broadcasts RequestVote RPCs.\n"
        "A candidate wins election if it receives votes from a majority of servers in the cluster."
    )
    file_bytes = io.BytesIO(unique_doc_content.encode("utf-8"))
    upload_res = await async_client.post(
        f"/api/v1/workspaces/{ws_a_id}/documents",
        files={"file": ("Raft_Protocol_Guide.txt", file_bytes, "text/plain")},
        data={"title": "Raft Consensus Protocol Guide"},
    )
    assert upload_res.status_code == 201
    doc_a = upload_res.json()
    assert doc_a["workspace_id"] == ws_a_id
    assert doc_a["status"] == "ready"
    assert doc_a["chunk_count"] >= 1

    # Verify Workspace A has 1 document, and Workspace B has 0 documents
    docs_a_res = await async_client.get(f"/api/v1/workspaces/{ws_a_id}/documents")
    assert len(docs_a_res.json()["documents"]) == 1

    docs_b_res = await async_client.get(f"/api/v1/workspaces/{ws_b_id}/documents")
    assert len(docs_b_res.json()["documents"]) == 0

    # Query Workspace A: Should retrieve Raft info with grounded citation
    tutor_a_res = await async_client.post(
        f"/api/v1/workspaces/{ws_a_id}/tutor",
        json={"message": "What happens when a follower experiences a leader election timeout in Raft?"},
    )
    assert tutor_a_res.status_code == 200
    tutor_a_data = tutor_a_res.json()
    assert tutor_a_data["retrieval"]["grounded"] is True
    assert len(tutor_a_data["citations"]) >= 1
    assert tutor_a_data["citations"][0]["document_name"] == "Raft_Protocol_Guide.txt"
    assert tutor_a_data["citations"][0]["document_id"] == doc_a["id"]

    # Query Workspace B with the EXACT SAME QUESTION:
    # Workspace B has no documents, so it MUST refuse and return 0 citations
    tutor_b_res = await async_client.post(
        f"/api/v1/workspaces/{ws_b_id}/tutor",
        json={"message": "What happens when a follower experiences a leader election timeout in Raft?"},
    )
    assert tutor_b_res.status_code == 200
    tutor_b_data = tutor_b_res.json()
    assert tutor_b_data["retrieval"]["grounded"] is False
    assert len(tutor_b_data["citations"]) == 0
    assert "not contain enough information" in tutor_b_data["message"]["content"]
    assert "Raft_Protocol_Guide.txt" not in str(tutor_b_data["citations"])

    # Clean up both workspaces
    await async_client.delete(f"/api/v1/workspaces/{ws_a_id}")
    await async_client.delete(f"/api/v1/workspaces/{ws_b_id}")
