"""
LumoraAI - Adaptive Quiz Engine End-to-End Test Suite
Validates the full adaptive learning lifecycle:
1. Quiz session creation & DB persistence
2. Active session resumption (survives refresh / re-entry)
3. Question structure & answer concealment
4. Real BKT posterior updates (correct vs. incorrect)
5. Multi-signal knowledge gap recalculation
6. Topic mastery aggregation & snapshot persistence
7. Controlled next-question adaptation based on learner state
8. Quiz completion, scoring, and history retrieval
9. Cross-workspace isolation & security
10. Error & edge-case handling (empty workspace, duplicate submissions)
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.services.bkt_mastery import bkt_service
from backend.app.services.adaptive_question_selector import adaptive_question_selector
from backend.app.services.knowledge_gap_engine import knowledge_gap_engine
from backend.app.ai.gateway import ai_gateway
from backend.app.ai.types import TaskType


async def setup_test_workspace() -> str:
    ws_id = f"ws_quiz_e2e_{uuid.uuid4().hex[:8]}"
    await workspace_repo.create(
        workspace_id=ws_id,
        name="Distributed Systems & Cryptography",
        goal="Master Distributed Protocols and TLS",
        level="intermediate",
    )

    doc = await document_repo.create(
        workspace_id=ws_id,
        title="Network Security and Consensus",
        filename="security_consensus.pdf",
        file_type="pdf",
        file_size=2048,
        page_count=4,
        status="ready",
    )

    chunks = [
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "security_consensus.pdf",
            "chunk_index": 1,
            "page_number": 1,
            "heading": "TLS Handshake Protocol",
            "text": "The TLS Handshake Protocol authenticates communicating peers and negotiates a shared secret key using asymmetric cryptographic primitives before data transmission begins.",
            "token_count": 30,
            "embedding": [0.01] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "security_consensus.pdf",
            "chunk_index": 2,
            "page_number": 2,
            "heading": "Master Secret Derivation",
            "text": "The Master Secret is computed as a 48-byte pseudorandom value from the Premaster Secret and client/server random nonces using the TLS PRF based on HMAC-SHA256.",
            "token_count": 32,
            "embedding": [0.02] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "security_consensus.pdf",
            "chunk_index": 3,
            "page_number": 3,
            "heading": "Raft Leader Election",
            "text": "In Raft consensus, leader election uses randomized election timers between 150ms and 300ms to prevent split votes. A candidate must receive votes from a majority of nodes.",
            "token_count": 35,
            "embedding": [0.03] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "security_consensus.pdf",
            "chunk_index": 4,
            "page_number": 4,
            "heading": "Log Replication Invariants",
            "text": "The Log Matching Property in Raft ensures that if two logs contain an entry with the same index and term, then the logs are identical in all entries up through the given index.",
            "token_count": 38,
            "embedding": [0.04] * 768,
        },
    ]
    await chunk_repo.insert_chunks(chunks)
    return ws_id


@pytest.mark.asyncio
async def test_quiz_session_persistence_and_active_resumption():
    """Verifies that starting a quiz creates a real persisted session and active resumption survives page refresh."""
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. No active session initially
            initial_active = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/active")
            assert initial_active.status_code == 200
            assert initial_active.json() is None

            # 2. Start new quiz session
            res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes",
                json={"target_question_count": 3, "initial_difficulty": 2},
            )
            assert res.status_code == 201
            session_data = res.json()
            quiz_id = session_data["id"]
            assert session_data["status"] == "active"
            assert session_data["target_question_count"] == 3
            assert session_data["current_question"] is not None

            # 3. Simulate page refresh / re-entry via GET /quizzes/active
            active_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/active")
            assert active_res.status_code == 200
            active_data = active_res.json()
            assert active_data is not None
            assert active_data["id"] == quiz_id
            assert active_data["status"] == "active"
            assert active_data["current_question"]["id"] == session_data["current_question"]["id"]

            # 4. Verify session can be retrieved directly by ID
            direct_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}")
            assert direct_res.status_code == 200
            assert direct_res.json()["id"] == quiz_id
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_question_structure_and_answer_concealment():
    """Verifies public questions hide the answer key and provide 4 options with citations."""
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes",
                json={"target_question_count": 3, "initial_difficulty": 2},
            )
            assert res.status_code == 201
            data = res.json()
            q1 = data["current_question"]

            # Confirm answer concealment
            assert "correct_option" not in q1
            assert "explanation" not in q1

            # Check options structure
            assert len(q1["options"]) == 4
            keys = [opt["key"] for opt in q1["options"]]
            assert keys == ["A", "B", "C", "D"]
            for opt in q1["options"]:
                assert len(opt["text"]) > 0

            # Check citation metadata
            assert q1["document_name"] == "security_consensus.pdf"
            assert q1["page_number"] in [1, 2, 3, 4]
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_bkt_posterior_updates_correct_and_incorrect():
    """
    Verifies that real answer submissions trigger authoritative BKT updates:
    - Correct answer increases mastery probability
    - Incorrect answer decreases mastery probability
    """
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes",
                json={"target_question_count": 4, "initial_difficulty": 2},
            )
            assert res.status_code == 201
            session_data = res.json()
            quiz_id = session_data["id"]
            q1 = session_data["current_question"]

            # Fetch internal question to know correct answer
            q1_internal = await quiz_repo.get_question(q1["id"], ws_id)
            correct_opt = q1_internal["correct_option"]
            q1_concept = q1_internal["concept"]

            # 1. Submit CORRECT attempt on Question 1
            att1_res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}/attempt",
                json={"selected_option": correct_opt, "response_time_ms": 10500},
            )
            assert att1_res.status_code == 200
            att1_data = att1_res.json()
            assert att1_data["is_correct"] is True
            assert att1_data["response_time_ms"] == 10500

            # Verify BKT increased
            m1 = await bkt_repo.get_concept_mastery(ws_id, q1_concept)
            assert m1 is not None
            assert m1["p_mastery"] > bkt_service.p_l0, f"Expected p_mastery > 0.30, got {m1['p_mastery']}"
            assert m1["correct_count"] == 1
            assert m1["attempts_count"] == 1

            # 2. Submit INCORRECT attempt on Question 2
            q2 = att1_data["next_question"]
            assert q2 is not None
            q2_internal = await quiz_repo.get_question(q2["id"], ws_id)
            wrong_opt = "B" if q2_internal["correct_option"] != "B" else "C"
            q2_concept = q2_internal["concept"]

            att2_res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q2['id']}/attempt",
                json={"selected_option": wrong_opt, "response_time_ms": 35000},
            )
            assert att2_res.status_code == 200
            att2_data = att2_res.json()
            assert att2_data["is_correct"] is False

            # Verify BKT decreased or stayed below baseline
            m2 = await bkt_repo.get_concept_mastery(ws_id, q2_concept)
            assert m2 is not None
            assert m2["p_mastery"] < m1["p_mastery"], f"Expected incorrect p_mastery < correct p_mastery"
            assert m2["correct_count"] == 0
            assert m2["attempts_count"] == 1
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_knowledge_gap_and_topic_mastery_recalculation():
    """Verifies that knowledge gap priority and topic mastery are recalculated after each attempt."""
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes",
                json={"target_question_count": 2, "initial_difficulty": 2},
            )
            assert res.status_code == 201
            session_data = res.json()
            quiz_id = session_data["id"]
            q1 = session_data["current_question"]
            q1_internal = await quiz_repo.get_question(q1["id"], ws_id)

            # Submit incorrect answer to create a knowledge gap
            wrong_opt = "B" if q1_internal["correct_option"] != "B" else "C"
            await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}/attempt",
                json={"selected_option": wrong_opt, "response_time_ms": 42000},
            )

            # 1. Verify Knowledge Gap is persisted and prioritized
            gaps = await bkt_repo.list_knowledge_gaps(ws_id)
            assert len(gaps) >= 1
            top_gap = gaps[0]
            assert top_gap["concept"] == q1_internal["concept"]
            assert top_gap["gap_priority"] > 0.40
            assert top_gap["gap_status"] in {"developing", "needs_attention", "critical_gap"}

            # 2. Verify Topic Mastery is recalculated
            topic_records = await topic_mastery_repo.list_topic_mastery(ws_id)
            assert len(topic_records) >= 1
            t_record = topic_records[0]
            assert t_record["attempt_count"] >= 1
            assert "mastery_probability" in t_record

            # 3. Verify Topic Mastery Snapshot is recorded
            snapshots = await topic_mastery_repo.get_recent_snapshots(ws_id, "topic", t_record["topic"])
            assert len(snapshots) >= 1
            assert snapshots[0]["entity_id"] == t_record["topic"]
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_controlled_next_question_adaptation():
    """
    Demonstrates with a controlled test that learner evidence changes the next question target:
    1. Learner struggles on Concept A -> gap priority increases -> selector prioritizes Concept A
    2. Learner masters Concept A -> mastery increases -> selector shifts to breadth or advancement
    """
    available_concepts = [
        {"concept": "TLS Handshake Protocol", "topic": "Security"},
        {"concept": "Raft Leader Election", "topic": "Consensus"},
        {"concept": "Log Replication Invariants", "topic": "Consensus"},
    ]

    # Scenario 1: Learner has a critical gap on TLS Handshake
    evals_weak = [
        {
            "concept": "TLS Handshake Protocol",
            "topic": "Security",
            "p_mastery": 0.18,
            "gap_priority": 0.78,
            "status": "critical_gap",
        },
        {
            "concept": "Raft Leader Election",
            "topic": "Consensus",
            "p_mastery": 0.65,
            "gap_priority": 0.25,
            "status": "strong",
        },
    ]

    decision_weak = adaptive_question_selector.select_next_question_target(
        concept_evaluations=evals_weak,
        available_concepts=available_concepts,
        current_question_index=5,
        target_total_questions=5,
    )
    assert decision_weak.target_concept == "TLS Handshake Protocol"
    assert decision_weak.is_reinforcement is True
    assert decision_weak.difficulty == 1, "Expected Level 1 foundational difficulty for critical gap"

    # Scenario 2: Learner masters TLS Handshake Protocol after practice
    evals_mastered = [
        {
            "concept": "TLS Handshake Protocol",
            "topic": "Security",
            "p_mastery": 0.82,
            "gap_priority": 0.15,
            "status": "strong",
        },
        {
            "concept": "Raft Leader Election",
            "topic": "Consensus",
            "p_mastery": 0.75,
            "gap_priority": 0.20,
            "status": "strong",
        },
    ]

    decision_mastered = adaptive_question_selector.select_next_question_target(
        concept_evaluations=evals_mastered,
        available_concepts=available_concepts,
        current_question_index=5,
        target_total_questions=5,
    )
    # Since both are strong and unassessed concepts exist, it expands breadth or advances difficulty
    assert decision_mastered.is_reinforcement is False
    assert decision_mastered.difficulty >= 2


@pytest.mark.asyncio
async def test_quiz_completion_and_history():
    """Verifies that completing a quiz records final metrics, transitions status, and appears in history."""
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes",
                json={"target_question_count": 2, "initial_difficulty": 2},
            )
            assert res.status_code == 201
            data = res.json()
            quiz_id = data["id"]
            q1 = data["current_question"]

            # Answer question 1
            att1 = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}/attempt",
                json={"selected_option": "A", "response_time_ms": 8000},
            )
            assert att1.status_code == 200
            q2 = att1.json()["next_question"]

            # Answer question 2
            att2 = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q2['id']}/attempt",
                json={"selected_option": "B", "response_time_ms": 9000},
            )
            assert att2.status_code == 200
            assert att2.json()["is_quiz_completed"] is True

            # Complete quiz
            comp_res = await ac.post(f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/complete")
            assert comp_res.status_code == 200
            summary = comp_res.json()
            assert summary["status"] == "completed"
            assert summary["total_questions"] == 2
            assert "accuracy_percentage" in summary
            assert "concept_performance" in summary
            assert len(summary["concept_performance"]) >= 1

            # Active session should now be None
            active_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/active")
            assert active_res.status_code == 200
            assert active_res.json() is None

            # History includes completed session
            hist_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/history")
            assert hist_res.status_code == 200
            hist = hist_res.json()
            assert any(s["id"] == quiz_id and s["status"] == "completed" for s in hist["sessions"])
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_edge_cases_and_workspace_isolation():
    """Verifies edge cases: empty workspaces, duplicate attempts, and cross-workspace isolation."""
    ws_id = await setup_test_workspace()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Empty workspace rejection
            empty_ws_id = f"ws_empty_{uuid.uuid4().hex[:8]}"
            await workspace_repo.create(workspace_id=empty_ws_id, name="Empty Space", goal="Test Empty")
            empty_res = await ac.post(f"/api/v1/workspaces/{empty_ws_id}/quizzes", json={"target_question_count": 3})
            assert empty_res.status_code == 400
            assert "No indexed documents found" in empty_res.json()["detail"]
            await workspace_repo.delete(empty_ws_id)

            # 2. Duplicate submission on same question
            res = await ac.post(f"/api/v1/workspaces/{ws_id}/quizzes", json={"target_question_count": 3})
            assert res.status_code == 201
            quiz_id = res.json()["id"]
            q_id = res.json()["current_question"]["id"]

            first_att = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q_id}/attempt",
                json={"selected_option": "A", "response_time_ms": 5000},
            )
            assert first_att.status_code == 200

            dup_att = await ac.post(
                f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q_id}/attempt",
                json={"selected_option": "B", "response_time_ms": 5000},
            )
            assert dup_att.status_code == 400
            assert "already been answered" in dup_att.json()["detail"]

            # 3. Cross-workspace access rejection
            ws_other = f"ws_other_{uuid.uuid4().hex[:8]}"
            await workspace_repo.create(workspace_id=ws_other, name="Other Space", goal="Other Goal")
            cross_res = await ac.get(f"/api/v1/workspaces/{ws_other}/quizzes/{quiz_id}")
            assert cross_res.status_code == 404
            await workspace_repo.delete(ws_other)
    finally:
        await workspace_repo.delete(ws_id)


@pytest.mark.asyncio
async def test_ai_gateway_quiz_task_routing():
    """Verifies that the AI Gateway routes TaskType.QUIZ to secondary provider (openrouter) first, then gemini."""
    routing = ai_gateway.get_routing_order(TaskType.QUIZ)
    assert len(routing) >= 2
    assert routing[0] == "openrouter" or routing[0] == "openai_compatible"
    assert routing[1] == "gemini"
