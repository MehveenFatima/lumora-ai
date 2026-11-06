"""
Uploads survive restarts: the original is stored before processing, so a failed or interrupted
file can be processed again without uploading it a second time.
"""
import asyncio
import os
import uuid

import pytest

from backend.app.api.routes import documents as doc_routes
from backend.app.repositories.documents import document_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.services.storage import storage_service

NOTES = (
    b"Paging\nPaging divides memory into fixed-size pages and frames. The page table maps each virtual "
    b"page to a physical frame, so a process can use memory that is not contiguous.\n"
)


async def _workspace() -> str:
    ws_id = f"ws_up_{uuid.uuid4().hex[:8]}"
    await workspace_repo.create(workspace_id=ws_id, name="Uploads", goal="Test")
    return ws_id


async def _stored_doc(ws_id: str, status: str) -> dict:
    doc = await document_repo.create(
        workspace_id=ws_id, title="OS notes", filename="os_notes.txt", file_type="txt",
        file_size=len(NOTES), status=status,
    )
    path = await storage_service.upload_file(ws_id, doc["id"], "os_notes.txt", NOTES, "text/plain")
    return await document_repo.update_status(doc["id"], status=status, storage_path=path) or doc


async def _wait_ready(async_client, doc_id: str) -> dict:
    for _ in range(100):
        body = (await async_client.get(f"/api/v1/documents/{doc_id}")).json()
        if body["status"] in ("ready", "failed"):
            return body
        await asyncio.sleep(0.05)
    raise AssertionError("document never finished processing")


@pytest.mark.asyncio
async def test_a_failed_file_can_be_retried_without_uploading_again(async_client):
    ws_id = await _workspace()
    doc = await _stored_doc(ws_id, "failed")
    listed = (await async_client.get(f"/api/v1/documents/{doc['id']}")).json()
    assert listed["can_retry"] is True

    res = await async_client.post(f"/api/v1/documents/{doc['id']}/retry")
    assert res.status_code == 200 and res.json()["status"] == "processing"
    done = await _wait_ready(async_client, doc["id"])
    assert done["status"] == "ready" and done["chunk_count"] >= 1 and done["can_retry"] is False

    # Only failed files can be retried
    again = await async_client.post(f"/api/v1/documents/{doc['id']}/retry")
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_retry_without_a_stored_original_asks_for_a_new_upload(async_client):
    ws_id = await _workspace()
    doc = await document_repo.create(
        workspace_id=ws_id, title="Lost", filename="lost.txt", file_type="txt", file_size=10, status="failed"
    )
    assert (await async_client.get(f"/api/v1/documents/{doc['id']}")).json()["can_retry"] is False
    res = await async_client.post(f"/api/v1/documents/{doc['id']}/retry")
    assert res.status_code == 410


@pytest.mark.asyncio
async def test_a_file_rejected_while_the_uploader_waits_leaves_nothing_stored(async_client):
    ws_id = await _workspace()
    before = set(os.listdir(os.path.join("backend", "data", "documents", ws_id))) if os.path.isdir(
        os.path.join("backend", "data", "documents", ws_id)
    ) else set()
    res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        files={"file": ("empty.txt", b"   \n  ", "text/plain")},
    )
    assert res.status_code in (400, 422)
    folder = os.path.join("backend", "data", "documents", ws_id)
    after = set(os.listdir(folder)) if os.path.isdir(folder) else set()
    assert after == before


@pytest.mark.asyncio
async def test_other_users_cannot_retry_someone_elses_file(async_client):
    other_ws = f"ws_other_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=other_ws, name="Private", goal="x", owner_id="usr_someone_else")
    doc = await _stored_doc(other_ws, "failed")
    res = await async_client.post(f"/api/v1/documents/{doc['id']}/retry")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_interrupted_processing_is_resumed_from_the_stored_original(async_client):
    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if not pool:
        pytest.skip("Resuming after a restart uses the database")
    ws_id = await _workspace()
    doc = await _stored_doc(ws_id, "indexing")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET updated_at = NOW() - INTERVAL '30 minutes' WHERE id = $1", uuid.UUID(doc["id"])
        )
    result = await doc_routes.resume_stalled_documents()
    assert result["resumed"] >= 1
    done = await _wait_ready(async_client, doc["id"])
    assert done["status"] == "ready"

    # After too many attempts, the file is marked failed with a retry option instead of looping
    stuck = await _stored_doc(ws_id, "processing")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET updated_at = NOW() - INTERVAL '30 minutes', resume_count = $2 WHERE id = $1",
            uuid.UUID(stuck["id"]), doc_routes.MAX_RESUMES,
        )
    await doc_routes.resume_stalled_documents()
    body = (await async_client.get(f"/api/v1/documents/{stuck['id']}")).json()
    assert body["status"] == "failed" and body["can_retry"] is True
