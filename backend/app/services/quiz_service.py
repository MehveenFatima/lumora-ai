from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from backend.app.core.logging import get_logger
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.quizzes import quiz_repo
from backend.app.services.question_generator import question_generator_service, InsufficientContextError
from backend.app.services.adaptive_quiz_engine import adaptive_quiz_engine, AdaptiveDecision
from backend.app.schemas.quizzes import (
    QuizOptionSchema,
    QuizQuestionPublicResponse,
    QuizSessionResponse,
    QuizAttemptResultResponse,
    QuizSummaryResponse,
    TopicPerformanceSummary,
    DifficultyPerformanceSummary,
    ConceptPerformanceSchema,
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
        # 1. Validate Workspace
        ws = await workspace_repo.get_by_id(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' not found.")

        # 2. Create Session Record
        session = await quiz_repo.create_session(
            workspace_id=workspace_id,
            user_id=user_id,
            target_question_count=target_question_count,
        )
        session_id = session["id"]

        # 3. Generate 1st Question
        gen_q = await question_generator_service.generate_question(
            workspace_id=workspace_id,
            topic=topic,
            target_difficulty=initial_difficulty,
        )

        q_record = await quiz_repo.create_question(
            quiz_session_id=session_id,
            workspace_id=workspace_id,
            question_index=1,
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
            generation_metadata={"initial_difficulty": initial_difficulty},
        )

        public_q = self._to_public_question(q_record)

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
            current_question=public_q,
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

        # Find current unanswered question if not completed
        attempted_q_ids = {str(a["question_id"]) for a in attempts}
        current_q = None
        for q in questions:
            if str(q["id"]) not in attempted_q_ids:
                current_q = self._to_public_question(q)
                break

        return QuizSessionResponse(
            id=session["id"],
            workspace_id=session["workspace_id"],
            user_id=session["user_id"],
            status=session["status"],
            target_question_count=session["target_question_count"],
            current_question_index=len(attempts) + 1 if session["status"] == "active" else len(attempts),
            score=session["score"],
            correct_count=session["correct_count"],
            total_count=session["total_count"],
            average_response_time_ms=session["average_response_time_ms"],
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
        # 1. Verify Session & Question Ownership
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

        # 4. Record Attempt
        attempt = await quiz_repo.create_attempt(
            quiz_session_id=session_id,
            question_id=question_id,
            workspace_id=workspace_id,
            user_id=user_id,
            selected_option=user_key,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
        )

        # 5. Update Session Metrics
        all_attempts = existing_attempts + [attempt]
        total_count = len(all_attempts)
        correct_count = sum(1 for a in all_attempts if a["is_correct"])
        total_time = sum(a.get("response_time_ms", 0) for a in all_attempts)
        avg_time = int(total_time / total_count) if total_count > 0 else 0
        new_score = correct_count * 10

        target_count = session["target_question_count"]
        is_completed = (total_count >= target_count)

        await quiz_repo.update_session(
            session_id,
            score=new_score,
            correct_count=correct_count,
            total_count=total_count,
            current_question_index=total_count,
            average_response_time_ms=avg_time,
            status="completed" if is_completed else "active",
            completed_at=datetime.now(timezone.utc) if is_completed else None,
        )

        # 6. Adaptive Next Question Generation (if not completed)
        next_public_q = None
        adaptation_decision = None

        if not is_completed:
            all_questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
            current_diff = question.get("difficulty", 2)
            adaptation_decision = adaptive_quiz_engine.evaluate_next_step(
                session_attempts=all_attempts,
                session_questions=all_questions,
                current_difficulty=current_diff,
            )

            # Generate next question with adapted difficulty/concept
            gen_q = await question_generator_service.generate_question(
                workspace_id=workspace_id,
                topic=adaptation_decision.target_topic,
                concept=adaptation_decision.target_concept,
                target_difficulty=adaptation_decision.next_difficulty,
            )

            next_q_record = await quiz_repo.create_question(
                quiz_session_id=session_id,
                workspace_id=workspace_id,
                question_index=total_count + 1,
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
                generation_metadata=adaptation_decision.to_dict(),
            )
            next_public_q = self._to_public_question(next_q_record)

        # Citation metadata
        cit = question.get("citation_metadata") or {}

        return QuizAttemptResultResponse(
            attempt_id=attempt["id"],
            question_id=question_id,
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
            next_question=next_public_q,
            adaptation_metadata=adaptation_decision.to_dict() if adaptation_decision else None,
        )

    async def complete_quiz(
        self,
        workspace_id: str,
        session_id: str,
    ) -> QuizSummaryResponse:
        session = await quiz_repo.get_session(session_id, workspace_id)
        if not session:
            raise ValueError(f"Quiz session '{session_id}' not found.")

        attempts = await quiz_repo.list_attempts_by_session(session_id, workspace_id)
        questions = await quiz_repo.list_questions_by_session(session_id, workspace_id)
        questions_by_id = {str(q["id"]): q for q in questions}

        total_q = len(attempts)
        correct_q = sum(1 for a in attempts if a.get("is_correct"))
        accuracy = int(round((correct_q / total_q) * 100)) if total_q > 0 else 0
        total_time_ms = sum(a.get("response_time_ms", 0) for a in attempts)
        avg_seconds = round((total_time_ms / (total_q * 1000)), 1) if total_q > 0 else 0.0

        # Mark completed
        now = datetime.now(timezone.utc)
        await quiz_repo.update_session(
            session_id,
            status="completed",
            completed_at=session.get("completed_at") or now,
        )

        # Topic Breakdown
        topic_stats: Dict[str, Dict[str, int]] = {}
        diff_stats: Dict[int, Dict[str, int]] = {1: {"total": 0, "correct": 0}, 2: {"total": 0, "correct": 0}, 3: {"total": 0, "correct": 0}}
        concept_stats: Dict[str, Dict[str, Any]] = {}

        for a in attempts:
            q = questions_by_id.get(str(a["question_id"]), {})
            t_name = q.get("topic", "General")
            c_name = q.get("concept", "General Concept")
            diff = q.get("difficulty", 2)
            is_c = a.get("is_correct", False)

            # Topic
            if t_name not in topic_stats:
                topic_stats[t_name] = {"total": 0, "correct": 0}
            topic_stats[t_name]["total"] += 1
            if is_c:
                topic_stats[t_name]["correct"] += 1

            # Difficulty
            if diff in diff_stats:
                diff_stats[diff]["total"] += 1
                if is_c:
                    diff_stats[diff]["correct"] += 1

            # Concept
            if c_name not in concept_stats:
                concept_stats[c_name] = {"topic": t_name, "total": 0, "correct": 0}
            concept_stats[c_name]["total"] += 1
            if is_c:
                concept_stats[c_name]["correct"] += 1

        topics_breakdown = []
        for t, st in topic_stats.items():
            acc = int(round((st["correct"] / st["total"]) * 100)) if st["total"] > 0 else 0
            status = "strong" if acc >= 75 else "developing" if acc >= 50 else "needs_review"
            topics_breakdown.append(
                TopicPerformanceSummary(
                    topic=t,
                    total_questions=st["total"],
                    correct=st["correct"],
                    accuracy_percentage=acc,
                    mastery_status=status,
                )
            )

        diff_labels = {1: "easy", 2: "medium", 3: "hard"}
        diff_breakdown = []
        for d, st in diff_stats.items():
            acc = int(round((st["correct"] / st["total"]) * 100)) if st["total"] > 0 else 0
            diff_breakdown.append(
                DifficultyPerformanceSummary(
                    difficulty=d,
                    difficulty_label=diff_labels[d],
                    total_questions=st["total"],
                    correct=st["correct"],
                    accuracy_percentage=acc,
                )
            )

        concept_performance = []
        knowledge_gaps = []
        for c, st in concept_stats.items():
            acc = int(round((st["correct"] / st["total"]) * 100)) if st["total"] > 0 else 0
            status = "strong" if acc >= 75 else "developing" if acc >= 50 else "needs_review"
            concept_performance.append(
                ConceptPerformanceSchema(
                    concept_name=c,
                    topic_name=st["topic"],
                    attempts=st["total"],
                    correct=st["correct"],
                    accuracy_percentage=acc,
                    status=status,
                )
            )
            if acc < 60:
                knowledge_gaps.append(c)

        recommendation = (
            f"Focus on reviewing {', '.join(knowledge_gaps[:2])} with the AI Tutor to reinforce foundational principles."
            if knowledge_gaps
            else "Excellent mastery demonstrated across all assessed topics! Proceed to higher difficulty challenges."
        )

        return QuizSummaryResponse(
            session_id=session_id,
            workspace_id=workspace_id,
            status="completed",
            total_questions=total_q,
            correct_count=correct_q,
            score=correct_q * 10,
            accuracy_percentage=accuracy,
            average_response_time_seconds=avg_seconds,
            topics_breakdown=topics_breakdown,
            difficulty_breakdown=diff_breakdown,
            concept_performance=concept_performance,
            knowledge_gaps_identified=knowledge_gaps,
            recommendation=recommendation,
            completed_at=now,
        )

    async def get_quiz_history(
        self,
        workspace_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> QuizHistoryResponse:
        sessions = await quiz_repo.list_sessions_by_workspace(workspace_id, limit, offset)
        items = []
        for s in sessions:
            total_q = s.get("total_count", 0)
            correct_q = s.get("correct_count", 0)
            acc = int(round((correct_q / total_q) * 100)) if total_q > 0 else 0
            avg_sec = round((s.get("average_response_time_ms", 0) / 1000), 1)
            items.append(
                QuizHistoryItemResponse(
                    id=s["id"],
                    workspace_id=s["workspace_id"],
                    status=s["status"],
                    total_questions=total_q,
                    correct_count=correct_q,
                    score=s.get("score", 0),
                    accuracy_percentage=acc,
                    average_response_time_seconds=avg_sec,
                    started_at=s.get("started_at"),
                    completed_at=s.get("completed_at"),
                )
            )
        return QuizHistoryResponse(sessions=items, total_count=len(items))

    def _to_public_question(self, q_dict: Dict[str, Any]) -> QuizQuestionPublicResponse:
        raw_options = q_dict.get("options", [])
        if isinstance(raw_options, str):
            import json
            raw_options = json.loads(raw_options)
        
        parsed_options = [
            QuizOptionSchema(key=opt.get("key", "A"), text=opt.get("text", ""))
            for opt in raw_options
        ]
        diff = q_dict.get("difficulty", 2)
        diff_label = {1: "easy", 2: "medium", 3: "hard"}.get(diff, "medium")
        cit = q_dict.get("citation_metadata") or {}

        return QuizQuestionPublicResponse(
            id=str(q_dict["id"]),
            quiz_session_id=str(q_dict["quiz_session_id"]),
            workspace_id=q_dict["workspace_id"],
            question_index=q_dict.get("question_index", 1),
            topic=q_dict.get("topic", "General"),
            concept=q_dict.get("concept", "Core Concept"),
            difficulty=diff,
            difficulty_label=diff_label,
            question_text=q_dict.get("question_text", ""),
            options=parsed_options,
            document_name=cit.get("document_name"),
            page_number=q_dict.get("page_number") or cit.get("page_number"),
            created_at=q_dict.get("created_at"),
        )


quiz_service = QuizService()
