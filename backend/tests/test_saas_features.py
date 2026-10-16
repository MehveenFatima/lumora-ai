"""
Background document processing, OCR for scanned pages, workspace search and notifications.
"""
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.routes import documents as documents_route
from backend.app.main import app
from backend.app.repositories.notifications import _memory_notifications
from backend.app.repositories.secondary import flashcard_repo
from backend.app.services import ocr as ocr_module
from backend.app.services.document_parser import ParsedPage, document_parser
from backend.app.services.embeddings import embedding_service
from backend.tests.conftest import TEST_USER_ID

NOTES = (
    b"Congestion Control\n\nCongestion control prevents the network from being overloaded. "
    b"TCP slow start doubles the congestion window every round-trip time until the threshold is reached. "
    b"After that, congestion avoidance increases the window by one segment per round-trip time."
)


@pytest.fixture(autouse=True)
def clean_notifications():
    _memory_notifications.clear()
    yield
    _memory_notifications.clear()


async def _new_workspace(client: AsyncClient) -> str:
    res = await client.post("/api/v1/workspaces", json={"name": f"Networks {uuid.uuid4().hex[:6]}", "goal": "Exam", "level": "beginner"})
    assert res.status_code in (200, 201)
    return res.json()["id"]


async def _upload(client: AsyncClient, ws_id: str, name: str = "networks.txt", data: bytes = NOTES, kind: str = "text/plain"):
    return await client.post(f"/api/v1/workspaces/{ws_id}/documents", files={"file": (name, data, kind)})


async def _wait_until_settled(client: AsyncClient, doc_id: str, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        doc = (await client.get(f"/api/v1/documents/{doc_id}")).json()
        if doc["status"] in ("ready", "failed") or asyncio.get_event_loop().time() > deadline:
            return doc
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------- background processing


@pytest.mark.asyncio
async def test_small_uploads_finish_inside_the_request(async_client):
    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id)
    assert res.status_code == 201
    assert res.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_slow_uploads_continue_in_the_background(async_client, monkeypatch):
    original = embedding_service.embed_documents

    async def slow_embed(texts):
        await asyncio.sleep(0.4)
        return await original(texts)

    monkeypatch.setattr(embedding_service, "embed_documents", slow_embed)
    monkeypatch.setattr(documents_route, "INGEST_WAIT_SECONDS", 0.05)

    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id)
    assert res.status_code == 202
    assert res.json()["status"] in ("processing", "extracting", "indexing")

    doc = await _wait_until_settled(async_client, res.json()["id"])
    assert doc["status"] == "ready" and doc["chunk_count"] >= 1

    notes = (await async_client.get("/api/v1/notifications")).json()["items"]
    assert any(n["type"] == "document_ready" and ws_id in (n["link"] or "") for n in notes)


@pytest.mark.asyncio
async def test_background_failures_are_recorded_not_lost(async_client, monkeypatch):
    async def broken_embed(texts):
        await asyncio.sleep(0.2)
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(embedding_service, "embed_documents", broken_embed)
    monkeypatch.setattr(documents_route, "INGEST_WAIT_SECONDS", 0.05)

    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id)
    assert res.status_code == 202
    doc = await _wait_until_settled(async_client, res.json()["id"])
    assert doc["status"] == "failed"
    assert "could not be processed" in doc["error_message"]
    assert "exploded" not in doc["error_message"]  # internal errors are not shown to users

    notes = (await async_client.get("/api/v1/notifications")).json()["items"]
    assert any(n["type"] == "document_failed" for n in notes)


@pytest.mark.asyncio
async def test_legacy_office_formats_get_a_clear_message(async_client):
    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id, "slides.ppt", b"\xd0\xcf\x11\xe0legacy", "application/vnd.ms-powerpoint")
    assert res.status_code == 400
    assert "Save As" in res.json()["detail"] and ".pptx" in res.json()["detail"]


# ---------------------------------------------------------------- OCR


def _minimal_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page()  # a blank page stands in for a scanned image
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.asyncio
async def test_scanned_pages_are_read_with_ocr(async_client, monkeypatch):
    seen = []

    async def fake_ocr(file_bytes, page_numbers):
        seen.extend(page_numbers)
        return [
            ParsedPage(page_number=n, text=f"Routing Algorithms\nLink state routing floods link information to every router (page {n}).", heading="Routing Algorithms")
            for n in page_numbers
        ]

    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_module, "ocr_pages", fake_ocr)

    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id, "scan.pdf", _minimal_pdf(), "application/pdf")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "ready" and body["page_count"] == 2
    assert seen == [1, 2]
    assert "read with OCR" in body["summary"]


@pytest.mark.asyncio
async def test_scanned_pdf_without_ocr_explains_why(async_client, monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: False)
    ws_id = await _new_workspace(async_client)
    res = await _upload(async_client, ws_id, "scan.pdf", _minimal_pdf(), "application/pdf")
    assert res.status_code == 422
    assert "No readable text" in res.json()["detail"]


def test_only_text_less_pages_need_ocr():
    pages = [ParsedPage(1, "A full page of typed notes about TCP and UDP."), ParsedPage(3, "short")]
    assert ocr_module.pages_needing_ocr(pages, 4) == [2, 3, 4]


# ---------------------------------------------------------------- search


@pytest.mark.asyncio
async def test_search_finds_topics_documents_flashcards_and_passages(async_client):
    ws_id = await _new_workspace(async_client)
    assert (await _upload(async_client, ws_id)).status_code == 201
    await flashcard_repo.save_flashcards(ws_id, [{
        "front": "What does TCP slow start do?", "back": "It doubles the congestion window every round-trip time.",
        "concept": "Congestion Control", "source_document": "networks.txt", "source_page": 1,
    }])

    res = await async_client.get(f"/api/v1/workspaces/{ws_id}/search", params={"q": "congestion"})
    assert res.status_code == 200
    results = res.json()["results"]
    types = {r["type"] for r in results}
    assert {"topic", "flashcard", "passage"} <= types
    assert all(r["link"].startswith(f"/dashboard/workspace/{ws_id}") for r in results)

    docs = (await async_client.get(f"/api/v1/workspaces/{ws_id}/search", params={"q": "networks"})).json()["results"]
    assert any(r["type"] == "document" for r in docs)

    assert (await async_client.get(f"/api/v1/workspaces/{ws_id}/search", params={"q": "x"})).json()["results"] == []


@pytest.mark.asyncio
async def test_search_is_scoped_to_the_owner(async_client):
    ws_id = await _new_workspace(async_client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as stranger:
        email = f"stranger-{uuid.uuid4().hex[:6]}@example.com"
        await stranger.post("/api/v1/auth/register", json={"name": "Other", "email": email, "password": "Str0ngPassw0rd"})
        res = await stranger.get(f"/api/v1/workspaces/{ws_id}/search", params={"q": "congestion"})
        assert res.status_code == 404


# ---------------------------------------------------------------- notifications


@pytest.mark.asyncio
async def test_quiz_gaps_and_due_cards_create_notifications(async_client):
    from backend.app.services.notification_service import notification_service

    ws_id = await _new_workspace(async_client)
    session = f"session-{uuid.uuid4().hex[:8]}"
    await notification_service.quiz_gaps(ws_id, session, 45.0, ["Paging", "TLB"])
    await notification_service.quiz_gaps(ws_id, session, 45.0, ["Paging", "TLB"])  # same quiz: stored once
    await flashcard_repo.save_flashcards(ws_id, [{"front": "What is paging?", "back": "Fixed-size memory blocks.", "concept": "Paging"}])

    body = (await async_client.get("/api/v1/notifications", params={"limit": 50})).json()
    here = [n for n in body["items"] if ws_id in (n["link"] or "")]
    kinds = [n["type"] for n in here]
    assert kinds.count("weak_topics") == 1
    assert "flashcards_due" in kinds
    weak = next(n for n in here if n["type"] == "weak_topics")
    assert "Paging" in weak["message"] and weak["link"].endswith("/study-plan")
    assert body["unread_count"] >= len(here)

    # Opening the list again does not duplicate today's reminder
    again = (await async_client.get("/api/v1/notifications", params={"limit": 50})).json()
    assert sum(1 for n in again["items"] if n["type"] == "flashcards_due" and ws_id in n["link"]) == 1

    assert (await async_client.post(f"/api/v1/notifications/{weak['id']}/read")).status_code == 204
    assert (await async_client.get("/api/v1/notifications")).json()["unread_count"] == body["unread_count"] - 1
    assert (await async_client.post("/api/v1/notifications/read-all")).status_code == 204
    assert (await async_client.get("/api/v1/notifications")).json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_notifications_are_private(async_client):
    from backend.app.services.notification_service import notification_service

    ws_id = await _new_workspace(async_client)
    await notification_service.quiz_gaps(ws_id, f"private-{uuid.uuid4().hex[:8]}", 30.0, ["Secret Topic"])
    mine = (await async_client.get("/api/v1/notifications", params={"limit": 50})).json()["items"]
    target = next(n for n in mine if n["type"] == "weak_topics" and ws_id in n["link"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as stranger:
        email = f"peek-{uuid.uuid4().hex[:6]}@example.com"
        await stranger.post("/api/v1/auth/register", json={"name": "Peek", "email": email, "password": "Str0ngPassw0rd"})
        theirs = (await stranger.get("/api/v1/notifications")).json()["items"]
        assert all("Secret Topic" not in n["message"] for n in theirs)
        assert (await stranger.post(f"/api/v1/notifications/{target['id']}/read")).status_code == 404
