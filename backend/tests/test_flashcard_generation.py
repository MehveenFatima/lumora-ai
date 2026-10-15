"""
Flashcards must read like study cards: a real question on the front, a short complete answer on
the back, and none of the PDF layout noise (card numbers, question numbers, file names).
"""
from types import SimpleNamespace

import pytest

from backend.app.ai.gateway import ai_gateway
from backend.app.services import secondary_service as svc_module
from backend.app.services.secondary_service import secondary_service
from backend.app.services.text_cleanup import clean_label, clean_study_text, truncate_at_sentence

NOISY_CHUNK = {
    "heading": "MWT · EJB (Unit III)",
    "text": (
        "MWT · EJB (Unit III) Card 1 front · Q1 Q2 Q5 Q9 Q1 Steps to build an EJB application "
        "EJB is a server-side component that holds the business logic and runs inside an EJB container.* "
        "The bean provider writes the Home and Remote interfaces; the container generates their implementation classes."
    ),
    "document_name": "MWT_Cheat_Cards (1).pdf",
    "page_number": 1,
}
NOISE = ["Card 1", "Q1", "Q2", "Q9", ".pdf", "*", "·"]


def test_cleanup_removes_layout_noise():
    text = clean_study_text(NOISY_CHUNK["text"], NOISY_CHUNK["heading"])
    for token in NOISE:
        assert token not in text
    assert "EJB is a server-side component" in text


def test_labels_drop_question_numbers():
    assert clean_label("Q1 Q2 Q5") is None
    assert clean_label("Card 3 back") is None
    assert clean_label("Q9 Session") == "Session"
    assert clean_label("MWT · EJB (Unit III)") == "EJB (Unit III)"


def test_truncation_never_cuts_a_word():
    text = "Paging maps virtual pages to physical frames. " * 10
    short = truncate_at_sentence(text, 120)
    assert len(short) <= 120 and short.endswith(".")
    assert truncate_at_sentence("word " * 60, 50).endswith("…")


def test_extractive_cards_ask_real_questions():
    sources = svc_module.SecondaryService._flashcard_sources([NOISY_CHUNK])
    cards = svc_module.SecondaryService._extractive_flashcards(sources)
    assert cards
    card = cards[0]
    assert card["front"].endswith("?")
    assert card["back"].endswith(".")
    for token in NOISE:
        assert token not in card["front"] and token not in card["back"]


@pytest.mark.asyncio
async def test_ai_cards_are_cleaned_and_linked_to_their_source(monkeypatch):
    async def fake_provider(request):
        assert "Q1 Q2" not in request.prompt  # the model never sees the layout noise
        return SimpleNamespace(structured_data={"cards": [
            {"front": "What is an EJB?", "back": "A server-side component that holds business logic.", "concept": "Enterprise JavaBeans", "source": 0},
            {"front": "Card 2 front · Q3 Who writes the Home interface?", "back": "The bean provider writes it.", "concept": "Q3 Q4", "source": 0},
            {"front": "not a question", "back": "ignored because the front is not a question", "source": 0},
        ]})

    monkeypatch.setattr(ai_gateway, "generate_structured", fake_provider)
    sources = secondary_service._flashcard_sources([NOISY_CHUNK])
    cards = await secondary_service._ai_flashcards(sources)

    assert [c["front"] for c in cards] == ["What is an EJB?", "Who writes the Home interface?"]
    assert cards[0]["concept"] == "Enterprise JavaBeans"
    assert cards[1]["concept"] == "EJB (Unit III)"  # falls back to the cleaned heading
    assert cards[0]["source_document"] == "MWT_Cheat_Cards (1).pdf" and cards[0]["source_page"] == 1


@pytest.mark.asyncio
async def test_legacy_decks_are_rebuilt(monkeypatch):
    store = {"cards": [{"id": f"old{i}", "front": f"What is the key mechanism of Q{i} Q{i+1}?", "back": "raw"} for i in range(8)]}

    async def list_cards(ws):
        return list(store["cards"])

    async def delete_cards(ws):
        store["cards"] = []

    async def save_cards(ws, cards):
        store["cards"] = [dict(c, id=f"new{i}") for i, c in enumerate(cards)]
        return store["cards"]

    async def docs(ws):
        return [{"id": "doc_1"}]

    async def chunks(ws, doc_id):
        return [NOISY_CHUNK] * 3

    async def no_ai(request):
        raise RuntimeError("provider unavailable")

    async def activity(**kwargs):
        return None

    monkeypatch.setattr(svc_module.flashcard_repo, "list_by_workspace", list_cards)
    monkeypatch.setattr(svc_module.flashcard_repo, "delete_by_workspace", delete_cards)
    monkeypatch.setattr(svc_module.flashcard_repo, "save_flashcards", save_cards)
    monkeypatch.setattr(svc_module.document_repo, "list_by_workspace", docs)
    monkeypatch.setattr(svc_module.chunk_repo, "get_chunks_by_document", chunks)
    monkeypatch.setattr(svc_module.activity_repo, "add_activity", activity)
    monkeypatch.setattr(ai_gateway, "generate_structured", no_ai)

    cards = await secondary_service.get_or_generate_flashcards("ws_legacy")
    assert cards and all(c["id"].startswith("new") for c in cards)
    assert not any(c["front"].startswith("What is the key mechanism of") for c in cards)
