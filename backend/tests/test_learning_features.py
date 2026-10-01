"""
Flashcard spaced repetition, question-format rules and the mastery history endpoint.
"""
from datetime import date, timedelta

import pytest

from backend.app.repositories.secondary import flashcard_repo
from backend.app.services.question_quality_validator import question_quality_validator
from backend.app.services.spaced_repetition import schedule_review

TODAY = date(2026, 10, 1)


def test_sm2_progression_and_reset():
    first = schedule_review("good", today=TODAY)
    assert (first.repetitions, first.interval_days, first.due_date) == (1, 1, TODAY + timedelta(days=1))

    second = schedule_review("good", first.repetitions, first.interval_days, first.ease_factor, today=TODAY)
    assert (second.repetitions, second.interval_days) == (2, 6)

    third = schedule_review("good", second.repetitions, second.interval_days, second.ease_factor, today=TODAY)
    assert third.interval_days == round(6 * third.ease_factor) or third.interval_days >= 14

    lapse = schedule_review("again", third.repetitions, third.interval_days, third.ease_factor, today=TODAY)
    assert (lapse.repetitions, lapse.interval_days, lapse.due_date) == (0, 0, TODAY)
    assert lapse.ease_factor == pytest.approx(max(1.3, third.ease_factor - 0.2))


def test_sm2_easy_beats_good_and_ease_floor():
    good = schedule_review("good", 2, 6, 2.5, today=TODAY)
    easy = schedule_review("easy", 2, 6, 2.5, today=TODAY)
    hard = schedule_review("hard", 2, 6, 2.5, today=TODAY)
    assert hard.interval_days < good.interval_days < easy.interval_days
    worst = schedule_review("hard", 5, 30, 1.3, today=TODAY)
    assert worst.ease_factor >= 1.3
    with pytest.raises(ValueError):
        schedule_review("perfect", today=TODAY)


@pytest.mark.asyncio
async def test_flashcard_review_endpoint_persists_schedule(async_client):
    import uuid

    card_id = f"fc_test_{uuid.uuid4().hex[:8]}"
    await flashcard_repo.save_flashcards(
        "os",
        [{"id": card_id, "front": "What does a page table map?", "back": "Virtual pages to physical frames.",
          "concept": "Paging", "source_document": "os.pdf", "source_page": 3}],
    )
    res = await async_client.post(f"/api/v1/workspaces/os/flashcards/{card_id}/review", json={"rating": "good"})
    assert res.status_code == 200
    body = res.json()
    assert body["repetitions"] == 1 and body["interval_days"] == 1 and body["review_count"] == 1
    assert body["last_rating"] == "good" and body["due_date"] > date.today().isoformat()

    again = await async_client.post(f"/api/v1/workspaces/os/flashcards/{card_id}/review", json={"rating": "again"})
    assert again.json()["repetitions"] == 0 and again.json()["due_date"] == date.today().isoformat()

    bad = await async_client.post(f"/api/v1/workspaces/os/flashcards/{card_id}/review", json={"rating": "meh"})
    assert bad.status_code == 422
    missing = await async_client.post("/api/v1/workspaces/os/flashcards/nope/review", json={"rating": "good"})
    assert missing.status_code == 404


def _opts(*texts):
    return [{"key": k, "text": t} for k, t in zip("ABCD", texts)]


@pytest.mark.parametrize(
    "options",
    [
        _opts("True", "False", "Sometimes true for large inputs", "Only on 64-bit systems"),
        _opts("A process control block", "A page table entry", "A file descriptor", "All of the above"),
        _opts("A process control block", "A page table entry", "A file descriptor", "None of these"),
        _opts("A process control block", "A page table entry", "Both A and B", "A file descriptor"),
    ],
)
def test_validator_rejects_true_false_and_aggregate_options(options):
    res = question_quality_validator.validate_question(
        question_text="Which structure does the kernel use to translate a virtual address during a memory access?",
        options=options,
        correct_option="B",
        concept="Paging",
    )
    assert not res.is_valid


def test_validator_rejects_unknown_difficulty_label():
    res = question_quality_validator.validate_question(
        question_text="Which structure does the kernel use to translate a virtual address during a memory access?",
        options=_opts("The process control block", "The page table", "The open file table", "The run queue"),
        correct_option="B",
        concept="Paging",
        difficulty="impossible",
    )
    assert any("difficulty" in r.lower() for r in res.rejection_reasons)


@pytest.mark.asyncio
async def test_mastery_history_tracks_quiz_progress(async_client):
    empty = await async_client.get("/api/v1/workspaces/dsa/mastery/history?days=7")
    assert empty.status_code == 200
    assert empty.json()["points"] == [] or all("mastery_percentage" in p for p in empty.json()["points"])

    from backend.app.services.topic_mastery_engine import topic_mastery_engine
    from backend.app.repositories.bkt import bkt_repo

    await bkt_repo.upsert_concept_mastery(
        workspace_id="dsa", topic="Graphs", concept="BFS", p_mastery=0.8, is_correct=True, response_time_ms=1000
    )
    await topic_mastery_engine.recalculate_all_workspace_topics("dsa")

    res = await async_client.get("/api/v1/workspaces/dsa/mastery/history?days=7")
    points = res.json()["points"]
    assert points and points[-1]["date"] == date.today().isoformat()
    assert 0 < points[-1]["mastery_percentage"] <= 100
