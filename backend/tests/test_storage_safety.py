import os

import pytest

from backend.app.services.storage import _safe_storage_name, storage_service


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("notes.pdf", "notes.pdf"),
        ("../../../../evil.txt", "evil.txt"),
        ("..\\..\\windows\\evil.pdf", "evil.pdf"),
        ("/etc/passwd", "passwd"),
        ("..", "document"),
        ("", "document"),
        (".hidden.txt", "hidden.txt"),
    ],
)
def test_safe_storage_name_strips_path_components(raw, expected):
    assert _safe_storage_name(raw) == expected


@pytest.mark.asyncio
async def test_upload_cannot_write_outside_document_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = await storage_service.upload_file(
        workspace_id="ws_storage_test",
        document_id="doc1",
        filename="../../../../escaped.txt",
        file_bytes=b"content",
        content_type="text/plain",
    )
    assert path == "workspace/ws_storage_test/documents/doc1/escaped.txt"
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "backend" / "escaped.txt").exists()
    assert (tmp_path / "backend" / "data" / "documents" / "ws_storage_test" / "doc1" / "escaped.txt").exists()

    # A stored path that tries to climb out of the storage root is never read from disk
    (tmp_path / "secret.txt").write_text("do not serve")
    assert await storage_service.get_file_bytes("workspace/x/documents/y/../../../../../secret.txt") is None
