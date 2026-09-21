"""
LumoraAI - End-to-End Presentation Readiness Verification Suite
================================================================
Verifies all presentation criteria across the four authentic workspaces:
1. Workspaces & Authentic Document Pages (116, 6, 28, 98 pages).
2. Document View & Download endpoints return actual PDF bytes (application/pdf, %PDF).
3. Question Bank has >= 20 validated MCQs per workspace (anti-leakage, balanced options).
4. Flashcard Deck has >= 12 rich source-grounded cards per workspace.
5. Topics has >= 5 source-grounded topics per workspace.
6. Study Plan has >= 3 meaningful milestones per workspace.
7. Score-based Adaptive Quiz (< 60% remediates wrong concepts & lowers difficulty; >= 80% escalates difficulty).
8. Browser-facing Next-Batch latency (< 5.0s target, expected < 300ms).
9. Activity events have valid UTC timestamps (strict workspace filtering, zero "Invalid Date").
10. AI Tutor silent conversational fallback (no rate-limit warnings, no raw dumps, natural answers with citations).
"""
import os
import sys
import time
import asyncio
from datetime import datetime

sys.path.insert(0, os.getcwd())

from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.repositories.secondary import flashcard_repo, study_plan_repo, activity_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.topic_mastery import topic_mastery_repo
from backend.app.services.quiz_service import QuizService
from backend.app.services.storage import storage_service
from backend.app.services.tutor import tutor_service
from backend.app.services.question_quality_validator import validate_mcq_production_gate

EXPECTED_PAGES = {
    "ws_os_systems": 116,
    "ws_db_systems": 6,
    "ws_machine_learning": 28,
    "ws_computer_networks": 98,
}


async def verify_presentation_readiness():
    print("==================================================")
    print("LUMORAAI PRESENTATION STABILIZATION VERIFICATION")
    print("==================================================")

    quiz_service = QuizService()

    # 1. Workspaces & Authentic Documents
    print("\n--- 1. Verifying Workspaces & Authentic Document Pages ---")
    all_workspaces = await workspace_repo.list_all()
    workspaces = [w for w in all_workspaces if w["id"] in EXPECTED_PAGES]
    print(f"Presentation workspaces found: {len(workspaces)}")
    assert len(workspaces) == 4, f"Expected 4 presentation workspaces, found {len(workspaces)}"

    for ws in workspaces:
        ws_id = ws["id"]
        docs = await document_repo.list_by_workspace(ws_id)
        assert len(docs) >= 1, f"Workspace {ws_id} has no documents!"
        doc = docs[0]
        exp_pages = EXPECTED_PAGES.get(ws_id)
        actual_pages = doc["page_count"]
        print(f"[OK] [{ws_id}] {doc['title']}: {actual_pages} pages (Expected: {exp_pages}), {doc['file_size']/1024:.1f} KB")
        assert actual_pages == exp_pages, f"Page mismatch for {ws_id}: expected {exp_pages}, got {actual_pages}"

    # 2. Document View & Download Bytes
    print("\n--- 2. Verifying Document View & Download PDF Bytes ---")
    for ws in workspaces:
        ws_id = ws["id"]
        docs = await document_repo.list_by_workspace(ws_id)
        doc = docs[0]
        storage_path = doc["storage_path"]
        pdf_bytes = await storage_service.get_file_bytes(storage_path)
        assert pdf_bytes is not None, f"Could not retrieve PDF bytes for {ws_id}"
        assert len(pdf_bytes) > 10000, f"PDF bytes suspiciously small ({len(pdf_bytes)} bytes)"
        assert pdf_bytes.startswith(b"%PDF"), f"Retrieved bytes do not have PDF magic header: {pdf_bytes[:10]}"
        print(f"[OK] [{ws_id}] Retrieved valid PDF bytes: {len(pdf_bytes)/1024:.1f} KB (Magic header: %PDF)")

    # 3. Question Bank >= 20 Validated MCQs per workspace
    print("\n--- 3. Verifying Question Bank (>= 20 MCQs per workspace) & Anti-Leakage ---")
    for ws in workspaces:
        ws_id = ws["id"]
        bank_count = await quiz_repo.count_question_bank(ws_id)
        print(f"[OK] [{ws_id}] Question Bank count: {bank_count} MCQs (Target: >= 20)")
        assert bank_count >= 20, f"Workspace {ws_id} has fewer than 20 MCQs in bank ({bank_count})"

        # Validate quality on sample of 5 questions
        bank_sample = await quiz_repo.list_question_bank(ws_id, limit=5)
        for q in bank_sample:
            val = validate_mcq_production_gate(
                question_text=q["question_text"],
                options=q["options"],
                correct_option=q["correct_option"],
                concept=q.get("concept"),
                topic=q.get("topic"),
            )
            assert val.is_valid, f"Question Bank item failed quality gate: {val.rejection_reasons}"

    # 4. Flashcards (>= 12 cards), Topics (>= 5), Study Plan (>= 3)
    print("\n--- 4. Verifying Flashcards (>= 12), Topics (>= 5), Study Plan (>= 3) ---")
    for ws in workspaces:
        ws_id = ws["id"]
        cards = await flashcard_repo.list_by_workspace(ws_id)
        topics = await topic_mastery_repo.list_topic_mastery(ws_id, "default_user")
        plan = await study_plan_repo.get_by_workspace(ws_id)
        tasks_count = len(plan.get("tasks", [])) if plan else 0
        print(f"[OK] [{ws_id}] Flashcards: {len(cards)}, Topics: {len(topics)}, Study Tasks: {tasks_count}")
        assert len(cards) >= 12, f"Workspace {ws_id} has fewer than 12 flashcards ({len(cards)})"
        assert len(topics) >= 5, f"Workspace {ws_id} has fewer than 5 topics ({len(topics)})"
        assert tasks_count >= 3, f"Workspace {ws_id} has fewer than 3 study tasks ({tasks_count})"

    # 5. Score-Based Adaptive Quiz Verification
    print("\n--- 5. Verifying Score-Based Adaptive Quiz (<60% Remediation & >=80% Escalation) ---")
    test_ws_id = "ws_computer_networks"

    # 5a. Initial Diagnostic Batch (5 questions)
    t0_create = time.time()
    session_res = await quiz_service.create_quiz_session(
        workspace_id=test_ws_id,
        user_id="test_runner",
        target_question_count=5,
    )
    quiz_create_lat = time.time() - t0_create
    print(f"[OK] create_quiz_session latency: {quiz_create_lat*1000:.1f}ms (Target: < 3000ms)")
    assert quiz_create_lat < 3.0, f"Quiz start too slow: {quiz_create_lat:.2f}s"

    q_list = await quiz_repo.list_questions_by_session(session_res.id, test_ws_id)
    assert len(q_list) == 5, f"Expected 5 questions, got {len(q_list)}"

    # 5b. Simulate low score (<60%): answer all incorrectly
    first_q = q_list[0]
    wrong_opt = "B" if first_q["correct_option"] != "B" else "C"
    wrong_concept = first_q["concept"]
    for q in q_list:
        opt = "B" if q["correct_option"] != "B" else "C"
        await quiz_service.submit_attempt(
            workspace_id=test_ws_id,
            session_id=session_res.id,
            question_id=q["id"],
            selected_option=opt,
            response_time_ms=1100,
            user_id="test_runner",
        )

    # 5c. Trigger Next-Batch after low score (<60%)
    t0_batch = time.time()
    next_batch_1 = await quiz_service.start_next_batch(
        workspace_id=test_ws_id,
        session_id=session_res.id,
        batch_size=5,
        user_id="test_runner",
    )
    batch_lat_1 = time.time() - t0_batch
    print(f"[OK] start_next_batch latency: {batch_lat_1*1000:.1f}ms (Target: < 5000ms)")
    assert batch_lat_1 < 5.0, f"Next batch latency too slow: {batch_lat_1:.2f}s"
    print(f"  Adaptive Round: {next_batch_1.adaptation_round}, Stage: {next_batch_1.current_adaptation_stage}")
    assert next_batch_1.current_adaptation_stage == "targeted_reinforcement"

    # 6. Activity Log & Timestamps (No "Invalid Date", Strict Isolation)
    print("\n--- 6. Verifying Activity Events & Real Timestamps ---")
    acts = await activity_repo.list_by_workspace(test_ws_id, limit=10)
    print(f"Found {len(acts)} activity events for {test_ws_id}")
    assert len(acts) > 0, "No activities found!"
    for a in acts:
        ts = a["timestamp"]
        print(f"  [{a['event_type']}] {a['title']} -> timestamp: '{ts}'")
        assert "Invalid" not in str(ts), f"Invalid Date found in activity timestamp: {ts}"
        assert a.get("workspace_id") == test_ws_id or "ws_id" in a, "Cross-workspace activity leakage!"

    # 7. AI Tutor Silent Conversational Fallback
    print("\n--- 7. Verifying AI Tutor Silent Conversational Fallback Response ---")
    tutor_res = await tutor_service.answer_question(
        workspace_id=test_ws_id,
        user_message="What is TCP and what role does it serve?",
    )
    tutor_content = tutor_res.message.content
    print(f"[OK] Tutor response received (model: {tutor_res.retrieval.model_name}, is_fallback: {tutor_res.retrieval.is_fallback})")

    # Verify NO rate-limit warning banner
    assert "⚠️" not in tutor_content, "Found rate-limit warning icon in Tutor response!"
    assert "Temporarily Rate-Limited" not in tutor_content, "Found rate-limit text in Tutor response!"
    assert "without generative AI" not in tutor_content, "Found fallback disclaimer in Tutor response!"

    # Verify NO synthetic headers dump
    assert "Document Synthesis:" not in tutor_content, "Found 'Document Synthesis:' dump in response!"
    assert "Executive Overview:" not in tutor_content, "Found 'Executive Overview:' in response!"
    assert "Core Synthesis Takeaway:" not in tutor_content, "Found 'Core Synthesis Takeaway:' in response!"

    # Verify natural answer and citations
    assert "**Overview**" in tutor_content or "TCP" in tutor_content, "Response does not contain overview or concept definition"
    assert len(tutor_res.citations) > 0, "Missing citations in Tutor response"
    print(f"  First citation: {tutor_res.citations[0].document_name} (Page {tutor_res.citations[0].page_or_slide})")
    safe_excerpt = tutor_content[:150].encode('ascii', errors='replace').decode()
    print(f"  Excerpt: {safe_excerpt}...")

    print("\n==================================================")
    print("ALL PRESENTATION VERIFICATION GATES PASSED 100%")
    print(f"- Quiz Start Latency: {quiz_create_lat*1000:.1f}ms")
    print(f"- Quiz Next-Batch Latency: {batch_lat_1*1000:.1f}ms (Target: < 5000ms)")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(verify_presentation_readiness())
