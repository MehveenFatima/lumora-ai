import pytest
from backend.app.services.document_parser import document_parser


def test_parse_plain_text():
    sample_text = b"Introduction to Graph Algorithms\n\nBreadth-First Search traverses level by level.\nDepth-First Search explores paths recursively."
    pages = document_parser.parse(sample_text, "txt")
    assert len(pages) >= 1
    assert "Graph Algorithms" in pages[0].text
    assert pages[0].page_number == 1


def test_parse_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported file type"):
        document_parser.parse(b"some data", "exe")
