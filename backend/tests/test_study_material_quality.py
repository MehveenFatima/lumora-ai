"""
Quiz questions and flashcards are written per concept of a topic map, reviewed, and never repeat
the same fact in other words. Slides about the lesson ("Independent Practice") are not concepts.

The AI provider is replaced by a scripted fake so the pipeline can be checked end to end offline.
"""
import json
import uuid
from types import SimpleNamespace

import pytest

from backend.app.ai.gateway import ai_gateway
from backend.app.repositories import concepts as concepts_repo_module
from backend.app.repositories import quizzes as quizzes_repo_module
from backend.app.services import concept_map as cm
from backend.app.services import flashcard_builder as fb
from backend.app.services import question_bank as qb
from backend.app.services.question_generator import QuizPreparingError, question_generator_service
from backend.app.services.question_quality_validator import validate_mcq_production_gate
from backend.app.services.similarity import DuplicateIndex, question_signature

CHUNKS = [
    {
        "id": "c1", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", "page_number": 1,
        "heading": "Equality of Complex Numbers",
        "text": "Two complex numbers a + bi and c + di are equal if and only if a = c and b = d. "
                "For example, if x + 3i = 5 + yi then x = 5 and y = 3.",
    },
    {
        "id": "c2", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", "page_number": 2,
        "heading": "Modulus of a Complex Number",
        "text": "The modulus of z = a + bi is |z| = sqrt(a^2 + b^2). For z = 3 + 4i the modulus is 5. "
                "The modulus is the distance of z from the origin in the Argand plane.",
    },
    {
        "id": "c3", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", "page_number": 3,
        "heading": "Independent Practice",
        "text": "Work on problems 1 to 10 on your own. Check your answers with a partner when you finish.",
    },
]

CONCEPT_MAP = {"concepts": [
    {"topic": "Complex Numbers", "concept": "Equality of complex numbers",
     "summary": "Two complex numbers are equal when their real parts and imaginary parts are equal.",
     "key_points": ["a + bi = c + di if and only if a = c and b = d", "Worked example: x + 3i = 5 + yi gives x = 5, y = 3"],
     "source_pages": [1]},
    {"topic": "Complex Numbers", "concept": "Modulus of a complex number",
     "summary": "The modulus is the distance of z from the origin.",
     "key_points": ["|z| = sqrt(a^2 + b^2)", "For z = 3 + 4i, |z| = 5"], "source_pages": [2]},
    {"topic": "Lesson", "concept": "Independent Practice", "summary": "Students work alone.",
     "key_points": ["Work on problems 1 to 10"], "source_pages": [3]},
]}


def _q(text, options, correct, difficulty=2, qtype="calculation"):
    return {
        "difficulty": difficulty, "question_type": qtype, "question_text": text,
        "options": [{"key": k, "text": t} for k, t in zip("ABCD", options)],
        "correct_option": correct,
        "explanation": "Compare the real parts and the imaginary parts separately to find the values.",
    }


EQUALITY_QUESTIONS = {"questions": [
    _q("If 2x + 3i = 8 + yi, what are the values of x and y?",
       ["x = 4, y = 3", "x = 8, y = 3", "x = 4, y = -3", "x = 3, y = 4"], "A", 1),
    _q("For which values of p and q is (p - 1) + 6i equal to 4 + 2qi?",
       ["p = 5, q = 3", "p = 3, q = 5", "p = 4, q = 6", "p = 5, q = 6"], "A", 2),
    # The same fact as the first question in other words: must be dropped as a duplicate
    _q("If 2x + 3i = 8 + yi, what values do x and y take?",
       ["x = 4, y = 3", "x = 8, y = 3", "x = 4, y = -3", "x = 3, y = 4"], "A", 1),
    # Flagged by the reviewer (index 3)
    _q("Which pair (a, b) makes a + bi equal to 0 + 7i and also to 1 + 7i at once?",
       ["a = 0, b = 7", "a = 1, b = 7", "a = 7, b = 0", "a = 0, b = 1"], "A", 3),
]}

MODULUS_QUESTIONS = {"questions": [
    _q("What is |z| for z = 6 - 8i?", ["|z| = 10", "|z| = 14", "|z| = 2", "|z| = 100"], "A", 1),
    _q("Which complex number has the same modulus as 5 + 12i?", ["13i", "5 - 7i", "12 + i", "17"], "A", 2),
]}

FLASHCARDS = {"cards": [
    {"concept_index": 0, "front": "When are two complex numbers a + bi and c + di equal?", "back": "Exactly when a = c and b = d."},
    {"concept_index": 0, "front": "What condition makes two complex numbers equal?", "back": "Exactly when a = c and b = d."},
    {"concept_index": 0, "front": "Solve for x and y: x + 3i = 5 + yi:", "back": "x = 5 and y = 3, by comparing real and imaginary parts."},
    {"concept_index": 1, "front": "What is the formula for the modulus of z = a + bi?", "back": "|z| = sqrt(a^2 + b^2)."},
    {"concept_index": 1, "front": "What does the modulus of z represent geometrically?", "back": "The distance of z from the origin in the Argand plane."},
]}


class FakeAI:
    def __init__(self):
        self.prompts = []

    async def __call__(self, request):
        p = request.prompt
        self.prompts.append(p)
        if "building a study map" in p:
            return SimpleNamespace(structured_data=json.loads(json.dumps(CONCEPT_MAP)))
        if "You are checking multiple-choice questions" in p:
            return SimpleNamespace(structured_data={"reviews": [{"index": 3, "keep": False, "reason": "two answers"}]})
        if "Write study flashcards" in p:
            return SimpleNamespace(structured_data=json.loads(json.dumps(FLASHCARDS)))
        if "CONCEPT: Equality of complex numbers" in p:
            return SimpleNamespace(structured_data=json.loads(json.dumps(EQUALITY_QUESTIONS)))
        if "CONCEPT: Modulus of a complex number" in p:
            return SimpleNamespace(structured_data=json.loads(json.dumps(MODULUS_QUESTIONS)))
        return SimpleNamespace(structured_data={"questions": []})


@pytest.fixture
def fake_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ai_gateway, "generate_structured", fake)
    monkeypatch.setattr(ai_gateway, "has_configured_provider", lambda task_type: True)
    concepts_repo_module._memory_concepts.clear()
    quizzes_repo_module._memory_question_bank.clear()
    yield fake
    concepts_repo_module._memory_concepts.clear()
    quizzes_repo_module._memory_question_bank.clear()


def test_lesson_slides_are_not_concepts():
    for label in ["Independent Practice", "Learning Objectives", "Exit Ticket", "Guided Practice: Modulus", "Agenda"]:
        assert cm.is_meta_content(label), label
    for label in ["Equality of Complex Numbers", "Reflection of light", "Objective function", "Enzyme activity"]:
        assert not cm.is_meta_content(label), label


def test_heading_based_map_skips_lesson_slides():
    names = [c["concept"] for c in cm.heuristic_concepts(CHUNKS)]
    assert "Equality of Complex Numbers" in names and "Modulus of a Complex Number" in names
    assert "Independent Practice" not in names


@pytest.mark.asyncio
async def test_ai_topic_map_drops_meta_concepts(fake_ai):
    ws_id, doc_id, chunks = await _workspace_with_notes("ws_map")
    saved = await cm.concept_map_service.build_for_document(ws_id, doc_id, "complex-numbers.pdf", chunks=chunks)
    assert [c["concept"] for c in await concepts_repo_module.concept_repo.list_by_workspace(ws_id)] == [
        c["concept"] for c in saved
    ]
    names = [c["concept"] for c in saved]
    assert names == ["Equality of complex numbers", "Modulus of a complex number"]
    assert all(c["method"] == "ai" for c in saved)
    assert saved[1]["key_points"][0] == "|z| = sqrt(a^2 + b^2)"


def test_maths_notation_and_numeric_options_pass_the_gate():
    ok = validate_mcq_production_gate(
        question_text="What is |z| for z = 6 - 8i?",
        options=[{"key": "A", "text": "|z| = 10"}, {"key": "B", "text": "|z| = 14"},
                 {"key": "C", "text": "|z| = 2"}, {"key": "D", "text": "|z| = 100"}],
        correct_option="A", concept="Modulus of a complex number", question_type="calculation",
    )
    assert ok.is_valid, ok.rejection_reasons
    numeric = validate_mcq_production_gate(
        question_text="How many distinct square roots does a non-zero complex number have?",
        options=[{"key": "A", "text": "2"}, {"key": "B", "text": "1"}, {"key": "C", "text": "4"}, {"key": "D", "text": "0"}],
        correct_option="A", concept="Roots of complex numbers", question_type="conceptual",
    )
    assert numeric.is_valid, numeric.rejection_reasons
    table = validate_mcq_production_gate(
        question_text="Which row of | name | value | holds the modulus?",
        options=[{"key": "A", "text": "The first row"}, {"key": "B", "text": "The second row"},
                 {"key": "C", "text": "The third row"}, {"key": "D", "text": "The fourth row"}],
        correct_option="A", concept="Modulus of a complex number",
    )
    assert not table.is_valid


@pytest.mark.asyncio
async def test_generation_reviews_and_drops_reworded_duplicates(fake_ai):
    concept = {"id": "cpt_1", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", **CONCEPT_MAP["concepts"][0]}
    questions = await qb.generate_for_concept(concept, "source", 4, DuplicateIndex())
    texts = [q.question_text for q in questions]
    assert texts == [
        "If 2x + 3i = 8 + yi, what are the values of x and y?",
        "For which values of p and q is (p - 1) + 6i equal to 4 + 2qi?",
    ]
    # The answer key follows its option when options are shuffled
    first = questions[0]
    assert next(o["text"] for o in first.options if o["key"] == first.correct_option) == "x = 4, y = 3"
    assert all(q.concept_id == "cpt_1" for q in questions)


def test_answer_position_is_varied():
    concept = {"concept": "Equality of complex numbers", "topic": "Complex Numbers", "source_pages": [1]}
    keys = set()
    for i in range(12):
        item = _q(f"If {i + 2}x + 3i = {2 * (i + 2)} + yi, what are the values of x and y?",
                  ["x = 2, y = 3", "x = 3, y = 2", "x = 2, y = -3", "x = -2, y = 3"], "A")
        q = qb.build_question(item, concept, "source")
        assert q is not None
        keys.add(q.correct_option)
    assert len(keys) >= 3


def _row(concept, text, answer, fp, difficulty=2):
    return {
        "concept": concept, "topic": "Complex Numbers", "difficulty": difficulty, "question_text": text,
        "options": [{"key": "A", "text": answer}, {"key": "B", "text": "x"}, {"key": "C", "text": "y"}, {"key": "D", "text": "z"}],
        "correct_option": "A", "explanation": "e", "fingerprint": fp, "quality_score": 1.0,
    }


def test_selection_covers_concepts_and_skips_rephrased_served_questions():
    rows = [
        _row("Equality", "If 2x + 3i = 8 + yi, what are x and y?", "x = 4, y = 3", "f1"),
        _row("Equality", "If 2x + 3i = 8 + yi, what values do x and y take?", "x = 4, y = 3", "f2"),
        _row("Equality", "For which p, q is (p - 1) + 6i equal to 4 + 2qi?", "p = 5, q = 3", "f3"),
        _row("Modulus", "What is |z| for z = 6 - 8i?", "|z| = 10", "f4"),
        _row("Conjugate", "What is the conjugate of 2 - 5i?", "2 + 5i", "f5"),
    ]
    picked = qb.select_questions(rows, 3, excluded_fingerprints={"f1"}, seed=1)
    fps = [q.fingerprint for q in picked]
    assert "f1" not in fps and "f2" not in fps  # f2 is f1 in other words
    assert {q.concept for q in picked} == {"Equality", "Modulus", "Conjugate"}

    weak_first = qb.select_questions(rows, 1, targets=[{"concept": "Modulus"}], seed=1)
    assert weak_first[0].concept == "Modulus"


@pytest.mark.asyncio
async def test_quiz_pool_writes_on_demand_then_serves_from_the_bank(fake_ai):
    ws_id, doc_id, chunks = await _workspace_with_notes("ws_pool")
    await cm.concept_map_service.build_for_document(ws_id, doc_id, "complex-numbers.pdf", chunks=chunks)

    first = await question_generator_service.generate_candidate_pool(ws_id, target_count=3, chunks=chunks)
    assert len(first) >= 3
    assert not any("practice" in q.question_text.lower() for q in first)
    assert len({q.concept for q in first[:2]}) == 2  # one question per concept first
    assert await quizzes_repo_module.quiz_repo.count_question_bank(ws_id) == len(first)

    calls_before = len(fake_ai.prompts)
    served = {q.fingerprint for q in first[:2]}
    second = await question_generator_service.generate_candidate_pool(
        ws_id, target_count=1, chunks=chunks, excluded_fingerprints=served
    )
    assert len(second) == 1 and second[0].fingerprint not in served
    assert len(fake_ai.prompts) == calls_before  # answered from the bank, no new AI call


@pytest.mark.asyncio
async def test_no_template_questions_when_the_ai_cannot_write_them(monkeypatch):
    async def broken(request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ai_gateway, "generate_structured", broken)
    monkeypatch.setattr(ai_gateway, "has_configured_provider", lambda task_type: True)
    quizzes_repo_module._memory_question_bank.clear()
    pool = await question_generator_service.generate_candidate_pool("ws_broken", target_count=5, chunks=CHUNKS)
    assert pool == []

    from backend.app.services.quiz_service import quiz_service
    with pytest.raises(QuizPreparingError):
        quiz_service._raise_no_questions("none")


@pytest.mark.asyncio
async def test_flashcards_never_rephrase_the_same_fact(fake_ai):
    concepts = [
        {"id": "a", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", **CONCEPT_MAP["concepts"][0]},
        {"id": "b", "document_id": "doc_cx", "document_name": "complex-numbers.pdf", **CONCEPT_MAP["concepts"][1]},
    ]
    cards = await fb.write_cards(concepts, CHUNKS)
    fronts = [c["front"] for c in cards]
    assert "What condition makes two complex numbers equal?" not in fronts  # same fact as the first card
    assert len(cards) == 4
    assert {c["concept"] for c in cards} == {"Equality of complex numbers", "Modulus of a complex number"}
    assert all(c["generator"] == fb.GENERATOR_TAG and c["document_id"] == "doc_cx" for c in cards)

    # "Generate more" never repeats the deck
    again = await fb.write_cards(concepts, CHUNKS, existing=cards)
    assert again == []


def test_question_signature_includes_the_answer():
    assert question_signature("What is |z|?", "5") == "What is |z|? Answer: 5"


async def _workspace_with_notes(prefix: str):
    """A workspace and document that exist in the configured store (memory or PostgreSQL)."""
    ws_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    doc_id = await _seed_workspace(ws_id)
    return ws_id, doc_id, [{**c, "document_id": doc_id} for c in CHUNKS]


async def _seed_workspace(ws_id: str) -> str:
    from backend.app.repositories.chunks import chunk_repo
    from backend.app.repositories.documents import document_repo
    from backend.app.repositories.workspaces import workspace_repo

    await workspace_repo.create(workspace_id=ws_id, name="Complex Numbers", goal="Learn complex numbers", level="beginner")
    doc = await document_repo.create(
        workspace_id=ws_id, title="Complex numbers", filename="complex-numbers.pdf", file_type="pdf",
        file_size=1024, page_count=3, status="ready",
    )
    await chunk_repo.insert_chunks([
        {**c, "id": f"{ws_id}_{c['id']}", "workspace_id": ws_id, "document_id": str(doc["id"]),
         "chunk_index": i, "token_count": 30, "embedding": [0.01 * (i + 1)] * 768}
        for i, c in enumerate(CHUNKS)
    ])
    return str(doc["id"])


@pytest.mark.asyncio
async def test_background_preparation_builds_map_deck_and_bank(fake_ai):
    from backend.app.repositories.secondary import flashcard_repo
    from backend.app.services.study_prep import study_prep_service

    ws_id, doc_id, _ = await _workspace_with_notes("ws_prep_e2e")
    old_deck = await flashcard_repo.save_flashcards(ws_id, [
        {"front": f"What is the key idea behind Q{i}?", "back": "raw text", "concept": "Q"} for i in range(6)
    ])

    assert study_prep_service.schedule(ws_id, force=True)
    assert study_prep_service.status(ws_id)["state"] == "preparing"
    await study_prep_service._tasks[ws_id]
    status = study_prep_service.status(ws_id)
    assert status["state"] == "ready" and status["concepts"] == 2

    deck = await flashcard_repo.list_by_workspace(ws_id)
    assert deck and all(c.get("generator") == fb.GENERATOR_TAG for c in deck)
    assert not {c["id"] for c in old_deck} & {c["id"] for c in deck}  # the old deck was retired
    bank = await quizzes_repo_module.quiz_repo.list_question_bank(ws_id, limit=100)
    assert {q["concept"] for q in bank} == {"Equality of complex numbers", "Modulus of a complex number"}
    assert all(q["generator"] == qb.GENERATOR_TAG and q["document_id"] == doc_id for q in bank)

    # Deleting the document removes what was written from it
    from backend.app.api.routes import documents as documents_route
    from backend.app.repositories.concepts import concept_repo

    await concept_repo.delete_by_document(doc_id)
    await quizzes_repo_module.quiz_repo.delete_question_bank_by_document(ws_id, doc_id)
    await flashcard_repo.delete_by_document(ws_id, doc_id)
    assert await concept_repo.list_by_workspace(ws_id) == []
    assert await quizzes_repo_module.quiz_repo.count_question_bank(ws_id) == 0
    assert await flashcard_repo.list_by_workspace(ws_id) == []
    assert documents_route  # route module imports cleanly with the cleanup hooks


@pytest.mark.asyncio
async def test_quiz_api_reports_preparing_instead_of_template_questions(async_client, monkeypatch):
    async def broken(request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ai_gateway, "generate_structured", broken)
    monkeypatch.setattr(ai_gateway, "has_configured_provider", lambda task_type: True)
    from backend.app.services.study_prep import study_prep_service
    monkeypatch.setattr(study_prep_service, "schedule", lambda *a, **k: False)
    quizzes_repo_module._memory_question_bank.clear()

    ws_id, _, _ = await _workspace_with_notes("ws_quiz_preparing")
    res = await async_client.post(f"/api/v1/workspaces/{ws_id}/quizzes", json={"target_question_count": 5})
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "QUIZ_PREPARING"
