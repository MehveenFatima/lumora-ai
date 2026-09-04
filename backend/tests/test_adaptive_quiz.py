import asyncio
import sys
import uuid
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.main import app
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.services.adaptive_quiz_engine import adaptive_quiz_engine
from backend.app.services.question_generator import question_generator_service, InsufficientContextError


def assert_true(condition: bool, message: str):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"  [OK] {message}")


async def setup_workspace():
    ws_id = f"ws_quiz_test_{uuid.uuid4().hex[:8]}"
    await workspace_repo.create(
        workspace_id=ws_id,
        name="Adaptive Quiz Test Track",
        goal="Verify Adaptive Quiz Engine",
        level="intermediate",
    )

    doc = await document_repo.create(
        workspace_id=ws_id,
        title="Computer Architecture & Systems",
        filename="sys_arch.pdf",
        file_type="pdf",
        file_size=1024,
        page_count=2,
        status="ready",
    )

    chunks = [
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "sys_arch.pdf",
            "chunk_index": 1,
            "page_number": 1,
            "heading": "Pipelining and Hazards",
            "text": "Instruction pipelining divides instruction execution into five stages: IF, ID, EX, MEM, WB. Structural hazards occur when hardware resources cannot support all concurrent instructions.",
            "token_count": 30,
            "embedding": [0.01] * 768,
        },
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "document_id": str(doc["id"]),
            "document_name": "sys_arch.pdf",
            "chunk_index": 2,
            "page_number": 2,
            "heading": "Cache Memory Hierarchies",
            "text": "Direct-mapped caches map each memory block to exactly one cache line. Set-associative caches divide the cache into sets of k lines, balancing hit time and conflict misses.",
            "token_count": 32,
            "embedding": [0.02] * 768,
        },
    ]
    await chunk_repo.insert_chunks(chunks)
    return ws_id


async def run_all_tests():
    print("\n===============================================================")
    print("  LUMORAAI — ADAPTIVE QUIZ ENGINE AUTOMATED SUITE")
    print("===============================================================\n")

    ws_id = await setup_workspace()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # TEST 1: Quiz Creation & Hidden Answer Key
        print("[TEST 1] Creating Quiz Session and verifying initial question structure...")
        res = await ac.post(
            f"/api/v1/workspaces/{ws_id}/quizzes",
            json={"target_question_count": 3, "initial_difficulty": 2},
        )
        assert_true(res.status_code == 201, "POST /api/v1/workspaces/{id}/quizzes returned HTTP 201")
        data = res.json()
        quiz_id = data["id"]
        assert_true(data["workspace_id"] == ws_id, f"Session workspace_id matches: '{data['workspace_id']}'")
        assert_true(data["target_question_count"] == 3, "Target question count is 3")

        q1 = data["current_question"]
        assert_true(q1 is not None, "Initial question is present")
        assert_true(len(q1["options"]) == 4, f"Exactly 4 options generated (got: {len(q1['options'])})")
        assert_true([opt["key"] for opt in q1["options"]] == ["A", "B", "C", "D"], "Option keys are ['A', 'B', 'C', 'D']")
        assert_true("correct_option" not in q1, "CRITICAL: correct_option is NOT exposed before submission")

        # TEST 2: GET Question hides answer
        print("\n[TEST 2] Verifying GET /questions/{id} hides answer key before attempt...")
        q_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}")
        assert_true(q_res.status_code == 200, "GET /questions/{id} returned HTTP 200")
        assert_true("correct_option" not in q_res.json(), "correct_option is absent from public question payload")

        # TEST 3: Submit Attempt & Reveal Correctness / Explanation
        print("\n[TEST 3] Submitting attempt and verifying answer reveal + next question...")
        att_res = await ac.post(
            f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}/attempt",
            json={"selected_option": "A", "response_time_ms": 12000},
        )
        assert_true(att_res.status_code == 200, "POST /attempt returned HTTP 200")
        att_data = att_res.json()
        assert_true("is_correct" in att_data, "Response reveals is_correct")
        assert_true("correct_option" in att_data, f"Response reveals correct_option: '{att_data['correct_option']}'")
        assert_true("explanation" in att_data and len(att_data["explanation"]) > 5, "Response contains grounded explanation")
        assert_true(att_data["response_time_ms"] == 12000, "Recorded exact response time 12000ms")
        assert_true(att_data["is_quiz_completed"] is False, "Quiz is not yet completed after question 1 of 3")
        assert_true(att_data["next_question"] is not None, "Next adaptive question is provided")
        assert_true("correct_option" not in att_data["next_question"], "Next question also hides correct_option")

        # TEST 4: Reject Duplicate Attempt on Same Question
        print("\n[TEST 4] Verifying duplicate attempt rejection...")
        dup_res = await ac.post(
            f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q1['id']}/attempt",
            json={"selected_option": "B", "response_time_ms": 5000},
        )
        assert_true(dup_res.status_code == 400, "Duplicate attempt correctly rejected with HTTP 400")

        # TEST 5: Answer Remaining Questions to Complete Quiz
        print("\n[TEST 5] Progressing through remaining adaptive questions...")
        q2 = att_data["next_question"]
        att2_res = await ac.post(
            f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q2['id']}/attempt",
            json={"selected_option": "A", "response_time_ms": 9000},
        )
        assert_true(att2_res.status_code == 200, "Question 2 attempt submitted")
        q3 = att2_res.json()["next_question"]

        att3_res = await ac.post(
            f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/questions/{q3['id']}/attempt",
            json={"selected_option": "C", "response_time_ms": 14000},
        )
        assert_true(att3_res.status_code == 200, "Question 3 attempt submitted")
        assert_true(att3_res.json()["is_quiz_completed"] is True, "Quiz completed after reaching target question count")

        # TEST 6: Complete & Calculate Aggregated Performance
        print("\n[TEST 6] Completing quiz and validating aggregated performance breakdown...")
        comp_res = await ac.post(f"/api/v1/workspaces/{ws_id}/quizzes/{quiz_id}/complete")
        assert_true(comp_res.status_code == 200, "POST /complete returned HTTP 200")
        summary = comp_res.json()
        assert_true(summary["session_id"] == quiz_id, "Summary session_id matches")
        assert_true(summary["status"] == "completed", "Status is 'completed'")
        assert_true(summary["total_questions"] == 3, f"Total questions is 3 (got: {summary['total_questions']})")
        assert_true("accuracy_percentage" in summary, f"Accuracy is {summary['accuracy_percentage']}%")
        assert_true("average_response_time_seconds" in summary, "Calculated average response time")
        assert_true(len(summary["topics_breakdown"]) > 0, "Generated topics breakdown")
        assert_true(len(summary["difficulty_breakdown"]) > 0, "Generated difficulty breakdown")
        assert_true("recommendation" in summary and len(summary["recommendation"]) > 5, "Generated AI recommendation")

        # TEST 7: Quiz History Retrieval
        print("\n[TEST 7] Retrieving quiz session history...")
        hist_res = await ac.get(f"/api/v1/workspaces/{ws_id}/quizzes/history")
        assert_true(hist_res.status_code == 200, "GET /history returned HTTP 200")
        hist = hist_res.json()
        assert_true(hist["total_count"] >= 1, f"Found {hist['total_count']} historical session(s)")
        assert_true(any(s["id"] == quiz_id for s in hist["sessions"]), "Current completed session is present in history")

        # TEST 8: Workspace Isolation & Security Enforcement
        print("\n[TEST 8] Verifying strict workspace isolation and cross-workspace access rejection...")
        ws_other = f"ws_other_{uuid.uuid4().hex[:8]}"
        await workspace_repo.create(workspace_id=ws_other, name="Other Isolated Track", goal="Isolation", level="beginner")

        # Cannot access ws_id quiz through ws_other
        bad_get = await ac.get(f"/api/v1/workspaces/{ws_other}/quizzes/{quiz_id}")
        assert_true(bad_get.status_code == 404, "Cross-workspace quiz access returned HTTP 404")

        # Cannot generate quiz in empty workspace
        empty_res = await ac.post(f"/api/v1/workspaces/{ws_other}/quizzes", json={"target_question_count": 3})
        assert_true(empty_res.status_code == 400, "Quiz generation on empty workspace rejected with HTTP 400")
        assert_true("No indexed documents found" in empty_res.json()["detail"], "Empty workspace error message is clear")

        await workspace_repo.delete(ws_other)

    # TEST 9: Adaptive Difficulty Progression Unit Scenarios
    print("\n[TEST 9] Verifying Adaptive Difficulty Algorithm signals...")
    engine = adaptive_quiz_engine

    # Fast + Correct -> Promotes difficulty
    q_u1 = {"id": "q1", "topic": "Pipelining", "concept": "Hazards", "difficulty": 1}
    dec_a = engine.evaluate_next_step([{"question_id": "q1", "is_correct": True, "response_time_ms": 8000}], [q_u1], current_difficulty=1)
    assert_true(dec_a.next_difficulty == 2, "Fast + Correct promoted difficulty 1 -> 2")

    # Slow + Incorrect -> Decreases difficulty
    q_u2 = {"id": "q2", "topic": "Caches", "concept": "Associativity", "difficulty": 3}
    dec_b = engine.evaluate_next_step([{"question_id": "q2", "is_correct": False, "response_time_ms": 52000}], [q_u2], current_difficulty=3)
    assert_true(dec_b.next_difficulty == 2, "Slow + Incorrect decreased difficulty 3 -> 2")

    # Repeated Mistake on Same Concept -> Triggers Reinforcement
    q_u3a = {"id": "q3a", "topic": "Pipelining", "concept": "Structural Hazards", "difficulty": 2}
    q_u3b = {"id": "q3b", "topic": "Pipelining", "concept": "Structural Hazards", "difficulty": 2}
    dec_c = engine.evaluate_next_step(
        [{"question_id": "q3a", "is_correct": False, "response_time_ms": 25000}, {"question_id": "q3b", "is_correct": False, "response_time_ms": 30000}],
        [q_u3a, q_u3b],
        current_difficulty=2,
    )
    assert_true(dec_c.is_reinforcement is True, "Repeated mistake triggered reinforcement")
    assert_true(dec_c.target_concept == "Structural Hazards", "Reinforcement targeted specific concept")

    # Cleanup test workspace
    await workspace_repo.delete(ws_id)

    print("\n===============================================================")
    print("  [SUCCESS] ALL 9 ADAPTIVE QUIZ ENGINE TEST SUITES PASSED!")
    print("===============================================================\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
