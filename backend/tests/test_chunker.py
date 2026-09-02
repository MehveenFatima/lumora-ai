import pytest
from backend.app.services.document_parser import ParsedPage
from backend.app.services.chunker import chunker_service


def test_chunk_pages_preserves_metadata():
    pages = [
        ParsedPage(page_number=1, text="Page 1 Content: Fundamentals of Dynamic Programming with memoization."),
        ParsedPage(page_number=2, text="Page 2 Content: 2D Grid DP and State Space Reduction techniques."),
    ]
    chunks = chunker_service.chunk_pages(
        workspace_id="dsa",
        document_id="doc_123",
        pages=pages,
        document_title="DP Masterclass",
    )

    assert len(chunks) == 2
    assert chunks[0].workspace_id == "dsa"
    assert chunks[0].document_id == "doc_123"
    assert chunks[0].page_number == 1
    assert "memoization" in chunks[0].text
    assert chunks[1].page_number == 2
    assert "State Space" in chunks[1].text
