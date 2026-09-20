"""
LumoraAI - Adaptive Quiz Service
Orchestrates diagnostic baseline generation, Bayesian Knowledge Tracing updates,
knowledge gap prioritization, candidate deduplication, and continuous multi-batch adaptation.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timezone
from backend.app.core.logging import get_logger
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.services.bkt_mastery import bkt_service
from backend.app.services.knowledge_gap_engine import knowledge_gap_engine
from backend.app.services.adaptive_question_selector import adaptive_question_selector
from backend.app.services.question_generator import (
    question_generator_service,
    NoIndexedDocumentsError,
    InsufficientContextError,
)
from backend.app.schemas.quizzes import (
    QuizOptionSchema,
    QuizQuestionPublicResponse,
    QuizSessionResponse,
    QuizAttemptResultResponse,
    QuizSummaryResponse,
    QuizNextBatchResponse,
    TopicPerformanceSummary,
    DifficultyPerformanceSummary,
    ConceptPerformanceSchema,
    KnowledgeGapDetail,
    QuizHistoryResponse,
    QuizHistoryItemResponse,
)

logger = get_logger(__name__)


class QuizService:
    async def create_quiz_session(
        self,
        workspace_id: str,
        user_id: str = "default_user",
        target_question_count: int = 5,
        topic: Optional[str] = None,
        initial_difficulty: int = 2,
    ) -> QuizSessionResponse:
        # 1. Validate Workspace Existence & Ownership
        ws = await workspace_repo.get_by_id(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' not found.")

        # 2. Check for Indexed Learning Materials (Empty Workspace Protection)
        available_concepts = await question_generator_service.extract_available_concepts(workspace_id)
        if not available_concepts:
            raise NoIndexedDocumentsError(
                f"No indexed learning materials are available in workspace '{workspace_id}'. Upload and index a resource before starting an adaptive quiz."
            )

        # 3. Create Session Record
        session = await quiz_repo.create_session(
            workspace_id=workspace_id,
            user_id=user_id,
            target_question_count=target_question_count,
        )
        session_id = session["id"]

        # Check existing learner model (BKT mastery + knowledge gaps)
        existing_gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)
        existing_mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        workspace_fps = set(await bkt_repo.list_workspace_fingerprints(workspace_id))

        if existing_gaps or existing_mastery:
            concept_evals = []
            for g in existing_gaps:
                concept_evals.append({
                    "concept": g["concept"],
                    "topic": g["topic"],
                    "gap_priority": g["gap_priority"],
                    "status": g["gap_status"],
                    "p_mastery": next((m["p_mastery"] for m in existing_mastery if m["concept"] == g["concept"]), bkt_service.p_l0),
                })
            gap_concept_names = {g["concept"] for g in existing_gaps}
            for m in existing_mastery:
                if m["concept"] not in gap_concept_names:
                    concept_evals.append({
                        "concept": m["concept"],
                        "topic": m.get("topic", "General"),
                        "gap_priority": round(1.0 - m.get("p_mastery", bkt_service.p_l0), 4),
                        "status": m.get("mastery_status", "developing"),
                        "p_mastery": m.get("p_mastery", bkt_service.p_l0),
                    })

            targets = adaptive_question_selector.select_batch_targets(
                concept_evaluations=concept_evals,
                available_concepts=available_concepts,
                batch_size=target_question_count,
            )
            target_concept_dicts = [{"concept": t.target_concept, "topic": t.target_topic} for t in targets]
            preferred_diff = targets[0].difficulty if targets else initial_difficulty
            stage = "targeted_reinforcement"
        else:
            target_concept_dicts = available_concepts
            preferred_diff = initial_difficulty
            stage = "diagnostic"

        # 4. Generate Initial Pool (Adapting to existing learner state if present)
        candidates = await question_generator_service.generate_candidate_pool(
            workspace_id=workspace_id,
            target_count=target_question_count,
            target_concepts=target_concept_dicts,
            excluded_fingerprints=workspace_fps,
            preferred_difficulty=preferred_diff,
        )

        if not candidates:
            raise InsufficientContextError("Could not generate sufficient unique diagnostic questions from workspace sources.")

        # Ensure we have target_question_count distinct questions
        selected_diagnostic = candidates[:target_question_count]

        # 5. Persist Initial Batch Questions & Fingerprints
        first_public_q = None
        for idx, gen_q in enumerate(selected_diagnostic, start=1):
            q_record = await quiz_repo.create_question(
                quiz_session_id=session_id,
                workspace_id=workspace_id,
                question_index=idx,
                topic=gen_q.topic,
                concept=gen_q.concept,
                difficulty=gen_q.difficulty,
                question_text=gen_q.question_text,
                options=gen_q.options,
                correct_option=gen_q.correct_option,
                explanation=gen_q.explanation,
                document_id=gen_q.document_id,
                page_number=gen_q.page_number,
                source_excerpt=gen_q.source_excerpt,
                citation_metadata={"document_name": gen_q.document_name, "page_number": gen_q.page_number},
                generation_metadata={"stage": "diagnostic", "fingerprint": gen_q.fingerprint},
                fingerprint=gen_q.fingerprint,
                question_type=getattr(gen_q, "question_type", "conceptual"),
                quality_score=getattr(gen_q, "quality_score", 1.0),
            )
            await bkt_repo.record_fingerprint(workspace_id, session_id, q_record["id"], gen_q.fingerprint)

            if idx == 1:
                first_public_q = self._to_public_question(q_record)

        return QuizSessionResponse(
            id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
            status=session["status"],
            target_question_count=target_question_count,
            current_question_index=1,
            score=0,
            correct_count=0,
            total_count=0,
            average_response_time_ms=0,
            adaptation_round=1,
            initial_diagnostic_completed=False,
            current_adaptation_stage="diagnostic",
            current_question=first_public_q,
            started_at=session["started_at"],
            created_at=session["created_at"],
        )

    async def get_quiz_session(
        self,
        workspace_id: str,
        session_id: str,
    ) -> Optional[QuizSessionResponse]:
        session = await quiz_repo.get_session(session_id, workspace_id)
        if not session:
            return None

        questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
        attempts = await quiz_repo.list_attempts_by_session(session_id, workspace_id)

        attempted_q_ids = {str(a["question_id"]) for a in attempts}
        current_q = None
        for q in questions:
            if str(q["id"]) not in attempted_q_ids:
                current_q = self._to_public_question(q)
                break

        return QuizSessionResponse(
            id=str(session["id"]),
            workspace_id=str(session["workspace_id"]),
            user_id=str(session["user_id"]),
            status=session["status"],
            target_question_count=session["target_question_count"],
            current_question_index=len(attempts) + 1 if session["status"] == "active" else len(attempts),
            score=session["score"],
            correct_count=session["correct_count"],
            total_count=session["total_count"],
            average_response_time_ms=session["average_response_time_ms"],
            adaptation_round=session.get("adaptation_round", 1),
            initial_diagnostic_completed=session.get("initial_diagnostic_completed", False),
            current_adaptation_stage=session.get("current_adaptation_stage", "diagnostic"),
            current_question=current_q,
            started_at=session.get("started_at"),
            completed_at=session.get("completed_at"),
            created_at=session.get("created_at"),
        )

    async def get_question(
        self,
        workspace_id: str,
        session_id: str,
        question_id: str,
    ) -> Optional[QuizQuestionPublicResponse]:
        q = await quiz_repo.get_question(question_id, workspace_id)
        if not q or str(q.get("quiz_session_id")) != session_id:
            return None
        return self._to_public_question(q)

    async def submit_attempt(
        self,
        workspace_id: str,
        session_id: str,
        question_id: str,
        selected_option: str,
        response_time_ms: int = 0,
        user_id: str = "default_user",
    ) -> QuizAttemptResultResponse:
        # 1. Verify Session & Question
        session = await quiz_repo.get_session(session_id, workspace_id)
        if not session:
            raise ValueError(f"Quiz session '{session_id}' not found in workspace '{workspace_id}'.")
        if session["status"] == "completed":
            raise ValueError(f"Quiz session '{session_id}' is already completed.")

        question = await quiz_repo.get_question(question_id, workspace_id)
        if not question or str(question.get("quiz_session_id")) != session_id:
            raise ValueError(f"Question '{question_id}' does not belong to session '{session_id}'.")

        # 2. Check Duplicate Attempt
        existing_attempts = await quiz_repo.list_attempts_by_session(session_id, workspace_id)
        if any(str(a["question_id"]) == question_id for a in existing_attempts):
            raise ValueError(f"Question '{question_id}' has already been answered in this session.")

        # 3. Evaluate Correctness
        correct_key = question["correct_option"].strip().upper()
        user_key = selected_option.strip().upper()
        is_correct = (user_key == correct_key)

        # 4. Record Attempt with Exact Duration
        attempt = await quiz_repo.create_attempt(
            quiz_session_id=session_id,
            question_id=question_id,
            workspace_id=workspace_id,
            user_id=user_id,
            selected_option=user_key,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
        )

        all_attempts = existing_attempts + [attempt]
        total_count = len(all_attempts)
        correct_count = sum(1 for a in all_attempts if a["is_correct"])
        total_time = sum(a.get("response_time_ms", 0) for a in all_attempts)
        avg_time = int(total_time / total_count) if total_count > 0 else 0
        new_score = correct_count * 10

        target_count = session["target_question_count"]
        is_completed = (total_count >= target_count)

        # 5. Authoritative BKT Concept Mastery Update
        concept_name = question.get("concept") or "Core Principle"
        topic_name = question.get("topic") or "General"

        mastery_record = await bkt_repo.get_concept_mastery(workspace_id, concept_name, user_id)
        current_p_k = mastery_record.get("p_mastery", bkt_service.p_l0) if mastery_record else bkt_service.p_l0
        new_p_k = bkt_service.update_mastery(current_p_k, is_correct)

        # 6. Multi-Signal Knowledge Gap Evaluation
        # Pull all historical attempts on this concept across the workspace for full sequential accuracy
        concept_attempts = await quiz_repo.list_attempts_by_concept(workspace_id, concept_name, user_id)
        if not concept_attempts:
            concept_attempts = [attempt]

        gap_info = knowledge_gap_engine.evaluate_concept_performance(
            concept=concept_name,
            topic=topic_name,
            p_mastery=new_p_k,
            attempts=concept_attempts,
        )

        # Atomic Transaction: update concept mastery and knowledge gap together
        await bkt_repo.upsert_concept_and_gap(
            workspace_id=workspace_id,
            topic=topic_name,
            concept=concept_name,
            p_mastery=new_p_k,
            is_correct=is_correct,
            gap_priority=gap_info["gap_priority"],
            gap_status=gap_info["status"],
            contributing_signals=gap_info["signals"],
            recommended_action=gap_info["recommended_action"],
            response_time_ms=response_time_ms,
            user_id=user_id,
        )

        # 6b. Topic Mastery Engine: Recalculate affected topic and snapshot
        try:
            from backend.app.services.topic_mastery_engine import topic_mastery_engine
            await topic_mastery_engine.recalculate_topic(
                workspace_id=workspace_id,
                topic=topic_name,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Error updating topic mastery in submit_attempt: {e}")

        # 7. Update Session State
        adaptation_round = session.get("adaptation_round", 1)
        initial_diag_done = session.get("initial_diagnostic_completed", False)
        if total_count >= 5:
            initial_diag_done = True

        await quiz_repo.update_session(
            session_id,
            score=new_score,
            correct_count=correct_count,
            total_count=total_count,
            current_question_index=total_count,
            average_response_time_ms=avg_time,
            status="completed" if is_completed else "active",
            initial_diagnostic_completed=initial_diag_done,
            completed_at=datetime.now(timezone.utc) if is_completed else None,
        )

        # 8. Find Next Unanswered Question in Current Batch
        next_public_q = None
        if not is_completed:
            session_questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
            attempted_ids = {str(a["question_id"]) for a in all_attempts}
            for q in session_questions:
                if str(q["id"]) not in attempted_ids:
                    next_public_q = self._to_public_question(q)
                    break

        cit = question.get("citation_metadata") or {}
        if isinstance(cit, str):
            import json
            try:
                cit = json.loads(cit)
            except Exception:
                cit = {}
        if not isinstance(cit, dict):
            cit = {}

        # Adaptation Explainability
        p_pct = int(round(new_p_k * 100))
        if is_correct:
            adapt_reason = f"BKT Mastery increased to {p_pct}% on '{concept_name}'."
        else:
            adapt_reason = f"BKT Mastery adjusted to {p_pct}%. Prioritizing '{concept_name}' for targeted review."

        return QuizAttemptResultResponse(
            attempt_id=str(attempt["id"]),
            question_id=str(question_id),
            selected_option=user_key,
            is_correct=is_correct,
            correct_option=correct_key,
            explanation=question.get("explanation", ""),
            document_name=cit.get("document_name"),
            page_number=question.get("page_number") or cit.get("page_number"),
            source_excerpt=question.get("source_excerpt"),
            response_time_ms=response_time_ms,
            current_score=new_score,
            current_question_index=total_count,
            target_question_count=target_count,
            is_quiz_completed=is_completed,
            adaptation_round=adaptation_round,
            next_question=next_public_q,
            adaptation_metadata={
                "adaptation_round": adaptation_round,
                "concept": concept_name,
                "p_mastery": new_p_k,
                "mastery_percentage": p_pct,
                "gap_priority": gap_info["gap_priority"],
                "gap_status": gap_info["status"],
                "reason": adapt_reason,
            },
        )

    async def start_next_batch(
        self,
        workspace_id: str,
        session_id: str,
        batch_size: int = 5,
        user_id: str = "default_user",
    ) -> QuizNextBatchResponse:
        """
        Advances the quiz session to the next adaptive batch (e.g. Batch 2: Targeted Reinforcement).
        Selects target concepts from knowledge gaps, generates new distinct candidates,
        and excludes all previous fingerprints and questions.
        """
        session = await quiz_repo.get_session(session_id, workspace_id)
        if not session:
            raise ValueError(f"Quiz session '{session_id}' not found in workspace '{workspace_id}'.")

        # 1. Gather BKT concept evaluations & knowledge gaps
        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)
        all_mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        available_concepts = await question_generator_service.extract_available_concepts(workspace_id)

        concept_evals = []
        for g in gaps:
            concept_evals.append({
                "concept": g["concept"],
                "topic": g["topic"],
                "gap_priority": g["gap_priority"],
                "status": g["gap_status"],
                "p_mastery": next((m["p_mastery"] for m in all_mastery if m["concept"] == g["concept"]), 0.3),
            })

        # 2. Select targeted batch targets
        targets = adaptive_question_selector.select_batch_targets(
            concept_evaluations=concept_evals,
            available_concepts=available_concepts,
            batch_size=batch_size,
        )

        # 3. Retrieve all previously seen fingerprints and question texts
        prev_fps = set(await bkt_repo.list_session_fingerprints(workspace_id, session_id))
        all_prev_questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
        prev_texts = [q["question_text"] for q in all_prev_questions]

        # 4. Generate new candidate pool strictly avoiding duplicates
        target_concept_dicts = [{"concept": t.target_concept, "topic": t.target_topic} for t in targets]
        candidates = await question_generator_service.generate_candidate_pool(
            workspace_id=workspace_id,
            target_count=batch_size,
            target_concepts=target_concept_dicts,
            excluded_fingerprints=prev_fps,
            excluded_texts=prev_texts,
            preferred_difficulty=targets[0].difficulty if targets else 2,
        )

        if not candidates:
            raise InsufficientContextError("Unable to generate new distinct questions for the next adaptive batch.")

        new_batch_questions = candidates[:batch_size]

        # 5. Persist new batch questions
        start_index = len(all_prev_questions) + 1
        new_q_records = []
        for offset, gen_q in enumerate(new_batch_questions):
            q_rec = await quiz_repo.create_question(
                quiz_session_id=session_id,
                workspace_id=workspace_id,
                question_index=start_index + offset,
                topic=gen_q.topic,
                concept=gen_q.concept,
                difficulty=gen_q.difficulty,
                question_text=gen_q.question_text,
                options=gen_q.options,
                correct_option=gen_q.correct_option,
                explanation=gen_q.explanation,
                document_id=gen_q.document_id,
                page_number=gen_q.page_number,
                source_excerpt=gen_q.source_excerpt,
                citation_metadata={"document_name": gen_q.document_name, "page_number": gen_q.page_number},
                generation_metadata={"stage": "targeted_reinforcement", "fingerprint": gen_q.fingerprint},
                fingerprint=gen_q.fingerprint,
                question_type=getattr(gen_q, "question_type", "conceptual"),
                quality_score=getattr(gen_q, "quality_score", 1.0),
            )
            await bkt_repo.record_fingerprint(workspace_id, session_id, q_rec["id"], gen_q.fingerprint)
            new_q_records.append(q_rec)

        # 6. Update session state for next batch
        next_round = session.get("adaptation_round", 1) + 1
        new_target_count = session["target_question_count"] + len(new_batch_questions)

        await quiz_repo.update_session(
            session_id,
            status="active",
            target_question_count=new_target_count,
            adaptation_round=next_round,
            initial_diagnostic_completed=True,
            current_adaptation_stage="targeted_reinforcement",
            completed_at=None,
        )

        first_q = self._to_public_question(new_q_records[0])
        target_concept_names = [t.target_concept for t in targets]

        return QuizNextBatchResponse(
            session_id=session_id,
            workspace_id=workspace_id,
            adaptation_round=next_round,
            current_adaptation_stage="targeted_reinforcement",
            target_concepts=target_concept_names,
            new_questions_count=len(new_batch_questions),
            first_question=first_q,
        )

    async def complete_quiz_session(
        self,
        workspace_id: str,
        session_id: str,
        user_id: str = "default_user",
    ) -> QuizSummaryResponse:
        session = await quiz_repo.get_session(session_id, workspace_id)
        if not session:
            raise ValueError(f"Quiz session '{session_id}' not found in workspace '{workspace_id}'.")

        questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
        attempts = await quiz_repo.list_attempts_by_session(session_id, workspace_id)

        now = datetime.now(timezone.utc)
        await quiz_repo.update_session(session_id, status="completed", completed_at=now)

        # Aggregations
        total_q = len(attempts) if attempts else session["total_count"]
        correct_q = sum(1 for a in attempts if a.get("is_correct"))
        accuracy = round((correct_q / total_q) * 100) if total_q > 0 else 0
        avg_time_sec = round((session["average_response_time_ms"] / 1000.0), 1)

        # BKT & Concept Breakdown
        concept_evals: List[ConceptPerformanceSchema] = []
        all_mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id)
        all_gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id)

        # Group attempts by concept
        attempts_by_concept: Dict[str, List[Dict[str, Any]]] = {}
        q_map = {str(q["id"]): q for q in questions}
        for a in attempts:
            q = q_map.get(str(a["question_id"]), {})
            c_name = q.get("concept") or "Core Principle"
            if c_name not in attempts_by_concept:
                attempts_by_concept[c_name] = []
            attempts_by_concept[c_name].append(a)

        for c_name, c_atts in attempts_by_concept.items():
            first_q = q_map.get(str(c_atts[0]["question_id"]), {})
            t_name = first_q.get("topic") or "General"
            m_record = next((m for m in all_mastery if m["concept"] == c_name), None)
            p_m = m_record["p_mastery"] if m_record else 0.30

            g_record = next((g for g in all_gaps if g["concept"] == c_name), None)
            g_priority = g_record["gap_priority"] if g_record else 0.50
            g_status = g_record["gap_status"] if g_record else "developing"

            c_correct = sum(1 for a in c_atts if a.get("is_correct"))
            c_acc = round((c_correct / len(c_atts)) * 100)

            concept_evals.append(
                ConceptPerformanceSchema(
                    concept_name=c_name,
                    topic_name=t_name,
                    attempts=len(c_atts),
                    correct=c_correct,
                    accuracy_percentage=c_acc,
                    p_mastery=p_m,
                    mastery_percentage=int(round(p_m * 100)),
                    gap_priority=g_priority,
                    status=g_status,
                    recommended_action="targeted_reinforcement" if g_status in {"critical_gap", "needs_attention"} else "continue_practice",
                )
            )

        # Topic Breakdown
        topic_map: Dict[str, List[Dict[str, Any]]] = {}
        for a in attempts:
            q = q_map.get(str(a["question_id"]), {})
            t = q.get("topic") or "General"
            if t not in topic_map:
                topic_map[t] = []
            topic_map[t].append(a)

        topic_summaries = []
        for t_name, t_atts in topic_map.items():
            t_total = len(t_atts)
            t_corr = sum(1 for a in t_atts if a.get("is_correct"))
            t_acc = round((t_corr / t_total) * 100)
            topic_summaries.append(
                TopicPerformanceSummary(
                    topic=t_name,
                    total_questions=t_total,
                    correct=t_corr,
                    accuracy_percentage=t_acc,
                    mastery_status="mastered" if t_acc >= 75 else ("proficient" if t_acc >= 50 else "needs_review"),
                )
            )

        # Difficulty Breakdown
        diff_map: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: []}
        for a in attempts:
            q = q_map.get(str(a["question_id"]), {})
            d = q.get("difficulty", 2)
            if d in diff_map:
                diff_map[d].append(a)

        diff_summaries = []
        for d_level, d_atts in diff_map.items():
            if d_atts:
                d_total = len(d_atts)
                d_corr = sum(1 for a in d_atts if a.get("is_correct"))
                d_acc = round((d_corr / d_total) * 100)
                diff_summaries.append(
                    DifficultyPerformanceSummary(
                        difficulty=d_level,
                        difficulty_label={1: "easy", 2: "medium", 3: "hard"}.get(d_level, "medium"),
                        total_questions=d_total,
                        correct=d_corr,
                        accuracy_percentage=d_acc,
                    )
                )

        # Structured Knowledge Gaps
        critical_gaps = [c for c in concept_evals if c.status in {"critical_gap", "needs_attention"}]
        gap_details = [
            KnowledgeGapDetail(
                concept=cg.concept_name,
                topic=cg.topic_name,
                gap_priority=cg.gap_priority or 0.5,
                status=cg.status,
                p_mastery=cg.p_mastery or 0.3,
                recommended_action=cg.recommended_action or "targeted_practice",
            )
            for cg in critical_gaps
        ]
        gap_names = [cg.concept_name for cg in critical_gaps]
        if gap_names:
            recommendation = f"Focus targeted review on {', '.join(gap_names[:2])} with the AI Tutor to close identified conceptual gaps."
        elif accuracy >= 80:
            recommendation = "Excellent mastery across evaluated concepts! Proceed to advanced validation questions."
        else:
            recommendation = "Good foundational performance. Continue practicing across varied curriculum topics."

        # Recalculate all workspace topics and sync learner profile
        try:
            from backend.app.services.topic_mastery_engine import topic_mastery_engine
            await topic_mastery_engine.recalculate_all_workspace_topics(workspace_id, user_id)
            from backend.app.services.learner_profile_service import learner_profile_service
            await learner_profile_service.get_learner_profile(workspace_id, user_id)
        except Exception as e:
            logger.warning(f"Error syncing learner profile on quiz completion: {e}")

        return QuizSummaryResponse(
            session_id=session_id,
            workspace_id=workspace_id,
            status="completed",
            target_question_count=session["target_question_count"],
            total_questions=total_q,
            correct_count=correct_q,
            score=session["score"],
            accuracy_percentage=accuracy,
            average_response_time_seconds=avg_time_sec,
            adaptation_round=session.get("adaptation_round", 1),
            topics_breakdown=topic_summaries,
            difficulty_breakdown=diff_summaries,
            concept_performance=concept_evals,
            knowledge_gaps=gap_details,
            knowledge_gaps_identified=gap_names,
            recommendation=recommendation,
            completed_at=now,
        )

    # Alias for complete_quiz_session
    complete_quiz = complete_quiz_session

    async def get_history(
        self,
        workspace_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> QuizHistoryResponse:
        sessions = await quiz_repo.list_sessions_by_workspace(workspace_id, limit=limit, offset=offset)
        items = []
        for s in sessions:
            total_q = s.get("total_count", 0)
            correct_q = s.get("correct_count", 0)
            acc = round((correct_q / total_q) * 100) if total_q > 0 else 0
            items.append(
                QuizHistoryItemResponse(
                    id=str(s["id"]),
                    workspace_id=s["workspace_id"],
                    status=s["status"],
                    target_question_count=s.get("target_question_count", 5),
                    total_questions=total_q,
                    correct_count=correct_q,
                    score=s.get("score", 0),
                    accuracy_percentage=acc,
                    average_response_time_seconds=round((s.get("average_response_time_ms", 0) / 1000.0), 1),
                    adaptation_round=s.get("adaptation_round", 1),
                    started_at=s.get("started_at"),
                    completed_at=s.get("completed_at"),
                )
            )
        return QuizHistoryResponse(sessions=items, total_count=len(items))

    async def get_active_session(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> Optional[QuizSessionResponse]:
        """
        Retrieves the latest active (uncompleted) quiz session for the workspace,
        along with its current unanswered question and attempts count.
        """
        session = await quiz_repo.get_active_session_by_workspace(workspace_id, user_id)
        if not session:
            return None
        return await self.get_quiz_session(workspace_id, str(session["id"]))

    def _to_public_question(self, q_record: Dict[str, Any]) -> QuizQuestionPublicResponse:
        diff = q_record.get("difficulty", 2)
        diff_label = {1: "easy", 2: "medium", 3: "hard"}.get(diff, "medium")

        cit = q_record.get("citation_metadata") or {}
        if isinstance(cit, str):
            import json
            try:
                cit = json.loads(cit)
            except Exception:
                cit = {}
        if not isinstance(cit, dict):
            cit = {}

        raw_opts = q_record.get("options", [])
        if isinstance(raw_opts, str):
            import json
            try:
                raw_opts = json.loads(raw_opts)
            except Exception:
                raw_opts = []
        if not isinstance(raw_opts, list):
            raw_opts = []

        options = [
            QuizOptionSchema(key=opt["key"], text=opt["text"])
            for opt in raw_opts
            if isinstance(opt, dict) and "key" in opt and "text" in opt
        ]

        gen_meta = q_record.get("generation_metadata") or {}
        if isinstance(gen_meta, str):
            import json
            try:
                gen_meta = json.loads(gen_meta)
            except Exception:
                gen_meta = {}
        if not isinstance(gen_meta, dict):
            gen_meta = {}

        q_type = q_record.get("question_type") or gen_meta.get("question_type") or "conceptual"

        return QuizQuestionPublicResponse(
            id=str(q_record["id"]),
            quiz_session_id=str(q_record["quiz_session_id"]),
            workspace_id=q_record["workspace_id"],
            question_index=q_record.get("question_index", 1),
            topic=q_record.get("topic", "General"),
            concept=q_record.get("concept", "Core Principle"),
            difficulty=diff,
            difficulty_label=diff_label,
            question_text=q_record.get("question_text", ""),
            options=options,
            document_name=cit.get("document_name") or q_record.get("document_name"),
            page_number=q_record.get("page_number") or cit.get("page_number"),
            fingerprint=q_record.get("fingerprint"),
            question_type=q_type,
            created_at=q_record.get("created_at"),
        )



quiz_service = QuizService()
