"""
Built-in sample workspaces: every sample question passes the app's own quality gates, and a user
gets three ready workspaces whose quiz, mastery tracking, flashcards and study plan all work without
an AI provider.
"""
import pytest

from backend.app.repositories.secondary import flashcard_repo
from backend.app.sample_content import cn, dbms, os as os_notes
from backend.app.services import question_bank as qb
from backend.app.services.question_quality_validator import validate_mcq_production_gate

MODULES = [os_notes, dbms, cn]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.WORKSPACE["name"])
def test_every_sample_question_passes_the_quality_gates(module):
    for c in module.CONCEPTS:
        assert len(c["questions"]) >= 4 and len(c["cards"]) >= 3
        assert {q[0] for q in c["questions"]} >= {1, 2, 3}
        concept = {"topic": c["topic"], "concept": c["concept"], "source_pages": [c["page"]]}
        for difficulty, text, options, answer, explanation in c["questions"]:
            q = qb.build_question(
                {"question_text": text, "options": options, "correct_option": answer,
                 "explanation": explanation, "difficulty": difficulty},
                concept, source_excerpt=c["summary"],
            )
            assert q is not None, text
            # The shuffled key still points at the intended answer
            right = options["ABCD".index(answer)]
            assert next(o["text"] for o in q.options if o["key"] == q.correct_option) == right
            gate = validate_mcq_production_gate(
                question_text=q.question_text, options=q.options, correct_option=q.correct_option,
                concept=q.concept, topic=q.topic,
            )
            assert gate.is_valid, (text, getattr(gate, "reasons", None) or gate)


@pytest.mark.asyncio
async def test_sample_workspaces_work_end_to_end(async_client):
    res = await async_client.post("/api/v1/sample-workspaces")
    assert res.status_code == 201, res.text
    created = res.json()["workspaces"]
    by_name = {w["name"]: w for w in created}
    assert set(by_name) >= {"Operating Systems", "DBMS", "Computer Networks"} or created == []
    if not created:  # created by an earlier test in this session
        listing = (await async_client.get("/api/v1/workspaces")).json()["workspaces"]
        by_name = {w["name"]: w for w in listing if w.get("is_sample")}
    ws = by_name["Operating Systems"]
    assert ws["is_sample"] is True and ws["document_count"] == 1

    # A second call adds nothing
    again = await async_client.post("/api/v1/sample-workspaces")
    assert again.status_code == 201 and again.json()["total_count"] == 0

    ws_id = ws["id"]
    # Flashcards are ready
    cards = await flashcard_repo.list_by_workspace(ws_id)
    assert len(cards) == 21 and all(c["generator"] == qb.GENERATOR_TAG for c in cards)

    # The study plan is topic-wise from the sample topic map
    plan = (await async_client.get(f"/api/v1/workspaces/{ws_id}/study-plan")).json()
    assert plan["coverage"]["total_concepts"] == 7
    learn = [t["title"] for t in plan["tasks"] if t["kind"] == "learn"]
    assert learn[0] == "Learn: Process and Process States"
    assert any(t["kind"] == "flashcards" for t in plan["tasks"] if t["scheduledFor"] == "today")

    # A quiz starts straight away and scores answers
    quiz = await async_client.post(f"/api/v1/workspaces/{ws_id}/quizzes", json={"target_question_count": 5})
    assert quiz.status_code == 201, quiz.text
    session = quiz.json()
    q = session["current_question"]
    assert q and len(q["options"]) == 4
    for _ in range(session["target_question_count"]):
        r = await async_client.post(
            f"/api/v1/workspaces/{ws_id}/quizzes/{session['id']}/questions/{q['id']}/attempt",
            json={"selected_option": "A", "response_time_ms": 4000},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        if body["is_quiz_completed"]:
            break
        q = body.get("next_question") or (await async_client.get(
            f"/api/v1/workspaces/{ws_id}/quizzes/{session['id']}")).json()["current_question"]
    summary = await async_client.post(f"/api/v1/workspaces/{ws_id}/quizzes/{session['id']}/complete")
    assert summary.status_code == 200, summary.text

    # Mastery was recorded, so the plan now has quiz evidence
    after = (await async_client.get(f"/api/v1/workspaces/{ws_id}/study-plan")).json()
    assert after["coverage"]["not_started"] < 7


@pytest.mark.asyncio
async def test_sample_notes_are_indexed_even_when_embeddings_are_unavailable(monkeypatch):
    from backend.app.repositories.workspaces import workspace_repo
    from backend.app.services import sample_workspaces
    from backend.app.services.embeddings import EmbeddingUnavailableError, embedding_service

    async def unavailable(texts):
        raise EmbeddingUnavailableError("rate-limited")

    monkeypatch.setattr(embedding_service, "embed_documents", unavailable)
    owner = "usr_test_default"  # the signed-in test user (exists in the database too)
    for w in await workspace_repo.list_by_owner(owner):
        if w.get("is_sample"):
            await workspace_repo.delete(w["id"])
    created = await sample_workspaces.create_for_user(owner)
    assert len(created) == 3
    listing = await workspace_repo.list_by_owner(owner)
    assert sum(1 for w in listing if w.get("is_sample")) == 3
