"""
Files larger than one request may carry on serverless hosting (Vercel: 4.5 MB) are uploaded in
parts. The parts are put back together exactly, a failed part can be sent again, and the finished
file is indexed like a direct upload.
"""
import uuid

import pytest

from backend.app.api.routes import documents as documents_route

PART = 1000
NOTES = (
    "Paging divides memory into fixed-size frames. A page table maps each virtual page to a frame. "
    "The TLB caches recent translations so most lookups avoid the page table. "
) * 40  # about 7 KB: several parts at the test part size


@pytest.fixture(autouse=True)
def small_parts(monkeypatch):
    monkeypatch.setattr(documents_route, "UPLOAD_CHUNK_BYTES", PART)
    documents_route._UPLOAD_SESSIONS.clear()
    yield
    documents_route._UPLOAD_SESSIONS.clear()


async def _workspace(client) -> str:
    res = await client.post("/api/v1/workspaces", json={"name": f"OS {uuid.uuid4().hex[:6]}", "goal": "Exam", "level": "beginner"})
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


async def _start(client, ws_id, data: bytes, name="paging.txt"):
    res = await client.post(f"/api/v1/workspaces/{ws_id}/uploads", json={"filename": name, "size": len(data), "title": "Paging"})
    assert res.status_code == 201, res.text
    return res.json()


def _parts(data: bytes):
    return [data[i:i + PART] for i in range(0, len(data), PART)]


@pytest.mark.asyncio
async def test_a_file_sent_in_parts_is_indexed(async_client):
    ws_id = await _workspace(async_client)
    data = NOTES.encode()
    upload = await _start(async_client, ws_id, data)
    assert upload["total_chunks"] == len(_parts(data))

    parts = list(enumerate(_parts(data)))
    for index, part in reversed(parts):  # order does not matter
        res = await async_client.put(
            f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/chunks/{index}",
            content=part, headers={"Content-Type": "application/octet-stream"},
        )
        assert res.status_code == 200, res.text
    # Sending a part again (a retry) is harmless
    index, part = parts[0]
    await async_client.put(f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/chunks/{index}", content=part)

    res = await async_client.post(f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/complete")
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["status"] == "ready" and doc["title"] == "Paging" and doc["file_size"] == len(data)

    # The upload is finished and cannot be completed twice
    again = await async_client.post(f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/complete")
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_missing_or_wrong_sized_parts_are_rejected(async_client):
    ws_id = await _workspace(async_client)
    data = NOTES.encode()
    upload = await _start(async_client, ws_id, data)
    base = f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}"

    short = await async_client.put(f"{base}/chunks/0", content=b"too short")
    assert short.status_code == 400
    out_of_range = await async_client.put(f"{base}/chunks/{upload['total_chunks']}", content=b"x")
    assert out_of_range.status_code == 400

    await async_client.put(f"{base}/chunks/0", content=_parts(data)[0])
    incomplete = await async_client.post(f"{base}/complete")
    assert incomplete.status_code == 400 and "missing" in incomplete.json()["detail"]


@pytest.mark.asyncio
async def test_uploads_are_validated_up_front_and_scoped_to_the_workspace(async_client):
    ws_id = await _workspace(async_client)
    other_ws = await _workspace(async_client)

    bad_type = await async_client.post(f"/api/v1/workspaces/{ws_id}/uploads", json={"filename": "x.exe", "size": 10})
    assert bad_type.status_code == 400
    too_big = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/uploads", json={"filename": "big.pdf", "size": 50 * 1024 * 1024}
    )
    assert too_big.status_code == 400

    upload = await _start(async_client, ws_id, NOTES.encode())
    wrong_ws = await async_client.put(
        f"/api/v1/workspaces/{other_ws}/uploads/{upload['upload_id']}/chunks/0", content=_parts(NOTES.encode())[0]
    )
    assert wrong_ws.status_code == 404


@pytest.mark.asyncio
async def test_a_corrupt_pdf_sent_in_parts_is_rejected(async_client):
    ws_id = await _workspace(async_client)
    data = b"not a pdf " * 300
    upload = await _start(async_client, ws_id, data, name="notes.pdf")
    for index, part in enumerate(_parts(data)):
        await async_client.put(f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/chunks/{index}", content=part)
    res = await async_client.post(f"/api/v1/workspaces/{ws_id}/uploads/{upload['upload_id']}/complete")
    assert res.status_code == 400 and "not a valid PDF" in res.json()["detail"]
