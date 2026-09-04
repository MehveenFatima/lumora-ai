from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime, timezone
import json
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage fallback
_memory_quiz_sessions: Dict[str, Dict[str, Any]] = {}
_memory_quiz_questions: Dict[str, Dict[str, Any]] = {}
_memory_quiz_attempts: Dict[str, Dict[str, Any]] = {}


class QuizRepository:
    async def create_session(
        self,
        workspace_id: str,
        user_id: str = "default_user",
        target_question_count: int = 5,
    ) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session_data = {
            "id": session_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "status": "active",
            "target_question_count": target_question_count,
            "current_question_index": 0,
            "score": 0,
            "correct_count": 0,
            "total_count": 0,
            "average_response_time_ms": 0,
            "adaptation_round": 1,
            "initial_diagnostic_completed": False,
            "current_adaptation_stage": "diagnostic",
            "current_target_concepts": [],
            "started_at": now,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO quiz_sessions 
                        (id, workspace_id, user_id, status, target_question_count, current_question_index, score, correct_count, total_count, average_response_time_ms, started_at, created_at, updated_at, adaptation_round, initial_diagnostic_completed, current_adaptation_stage)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                        """,
                        uuid.UUID(session_id),
                        workspace_id,
                        user_id,
                        session_data["status"],
                        target_question_count,
                        0,
                        0,
                        0,
                        0,
                        0,
                        now,
                        now,
                        now,
                        1,
                        False,
                        "diagnostic",
                    )
            except Exception as e:
                # If table does not yet have Phase 2 columns, fallback to base insert
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO quiz_sessions 
                            (id, workspace_id, user_id, status, target_question_count, current_question_index, score, correct_count, total_count, average_response_time_ms, started_at, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                            """,
                            uuid.UUID(session_id),
                            workspace_id,
                            user_id,
                            session_data["status"],
                            target_question_count,
                            0,
                            0,
                            0,
                            0,
                            0,
                            now,
                            now,
                            now,
                        )
                except Exception as inner_e:
                    logger.error(f"Error creating quiz session in DB: {inner_e}")

        _memory_quiz_sessions[session_id] = session_data
        return session_data

    async def get_session(
        self,
        session_id: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    query = "SELECT * FROM quiz_sessions WHERE id = $1"
                    params = [uuid.UUID(session_id) if len(session_id) == 36 else session_id]
                    if workspace_id:
                        query += " AND workspace_id = $2"
                        params.append(workspace_id)
                    row = await conn.fetchrow(query, *params)
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error(f"Error fetching quiz session from DB: {e}")

        session = _memory_quiz_sessions.get(session_id)
        if session and (not workspace_id or session["workspace_id"] == workspace_id):
            return session
        return None

    async def update_session(
        self,
        session_id: str,
        **fields,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        fields["updated_at"] = now

        pool = await get_db_pool()
        if pool:
            try:
                set_clauses = []
                values = [uuid.UUID(session_id) if len(session_id) == 36 else session_id]
                for idx, (k, v) in enumerate(fields.items(), start=2):
                    set_clauses.append(f"{k} = ${idx}")
                    values.append(v)
                
                query = f"UPDATE quiz_sessions SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(query, *values)
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error(f"Error updating quiz session in DB: {e}")

        if session_id in _memory_quiz_sessions:
            _memory_quiz_sessions[session_id].update(fields)
            return _memory_quiz_sessions[session_id]
        return None

    async def list_sessions_by_workspace(
        self,
        workspace_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM quiz_sessions 
                        WHERE workspace_id = $1 
                        ORDER BY started_at DESC 
                        LIMIT $2 OFFSET $3
                        """,
                        workspace_id,
                        limit,
                        offset,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing quiz sessions from DB: {e}")

        matching = [s for s in _memory_quiz_sessions.values() if s["workspace_id"] == workspace_id]
        matching.sort(key=lambda x: x.get("started_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return matching[offset : offset + limit]

    async def create_question(
        self,
        quiz_session_id: str,
        workspace_id: str,
        question_index: int,
        topic: str,
        concept: str,
        difficulty: int,
        question_text: str,
        options: List[Dict[str, str]],
        correct_option: str,
        explanation: str,
        document_id: Optional[str] = None,
        page_number: Optional[int] = None,
        source_excerpt: Optional[str] = None,
        citation_metadata: Optional[Dict[str, Any]] = None,
        generation_metadata: Optional[Dict[str, Any]] = None,
        fingerprint: Optional[str] = None,
        question_type: Optional[str] = "conceptual",
        quality_score: Optional[float] = 1.0,
    ) -> Dict[str, Any]:
        question_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        q_data = {
            "id": question_id,
            "quiz_session_id": quiz_session_id,
            "workspace_id": workspace_id,
            "question_index": question_index,
            "topic": topic,
            "concept": concept,
            "difficulty": difficulty,
            "question_text": question_text,
            "options": options,
            "correct_option": correct_option,
            "explanation": explanation,
            "document_id": document_id,
            "page_number": page_number,
            "source_excerpt": source_excerpt,
            "citation_metadata": citation_metadata or {},
            "generation_metadata": generation_metadata or {},
            "fingerprint": fingerprint,
            "question_type": question_type or "conceptual",
            "quality_score": quality_score if quality_score is not None else 1.0,
            "created_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO quiz_questions
                        (id, quiz_session_id, workspace_id, question_index, topic, concept, difficulty, question_text, options, correct_option, explanation, document_id, page_number, source_excerpt, citation_metadata, generation_metadata, created_at, fingerprint, question_type, quality_score)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                        """,
                        uuid.UUID(question_id),
                        uuid.UUID(quiz_session_id) if len(quiz_session_id) == 36 else quiz_session_id,
                        workspace_id,
                        question_index,
                        topic,
                        concept,
                        difficulty,
                        question_text,
                        json.dumps(options),
                        correct_option,
                        explanation,
                        uuid.UUID(document_id) if document_id and len(document_id) == 36 else None,
                        page_number,
                        source_excerpt,
                        json.dumps(citation_metadata or {}),
                        json.dumps(generation_metadata or {}),
                        now,
                        fingerprint,
                        question_type or "conceptual",
                        float(quality_score) if quality_score is not None else 1.0,
                    )
            except Exception as e:
                # Fallback if question_type/quality_score column not yet present
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO quiz_questions
                            (id, quiz_session_id, workspace_id, question_index, topic, concept, difficulty, question_text, options, correct_option, explanation, document_id, page_number, source_excerpt, citation_metadata, generation_metadata, created_at, fingerprint)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                            """,
                            uuid.UUID(question_id),
                            uuid.UUID(quiz_session_id) if len(quiz_session_id) == 36 else quiz_session_id,
                            workspace_id,
                            question_index,
                            topic,
                            concept,
                            difficulty,
                            question_text,
                            json.dumps(options),
                            correct_option,
                            explanation,
                            uuid.UUID(document_id) if document_id and len(document_id) == 36 else None,
                            page_number,
                            source_excerpt,
                            json.dumps(citation_metadata or {}),
                            json.dumps(generation_metadata or {}),
                            now,
                            fingerprint,
                        )
                except Exception as inner_e:
                    # Second fallback if fingerprint column not yet present
                    try:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                INSERT INTO quiz_questions
                                (id, quiz_session_id, workspace_id, question_index, topic, concept, difficulty, question_text, options, correct_option, explanation, document_id, page_number, source_excerpt, citation_metadata, generation_metadata, created_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                                """,
                                uuid.UUID(question_id),
                                uuid.UUID(quiz_session_id) if len(quiz_session_id) == 36 else quiz_session_id,
                                workspace_id,
                                question_index,
                                topic,
                                concept,
                                difficulty,
                                question_text,
                                json.dumps(options),
                                correct_option,
                                explanation,
                                uuid.UUID(document_id) if document_id and len(document_id) == 36 else None,
                                page_number,
                                source_excerpt,
                                json.dumps(citation_metadata or {}),
                                json.dumps(generation_metadata or {}),
                                now,
                            )
                    except Exception as inner_inner_e:
                        logger.error(f"Error creating quiz question in DB: {inner_inner_e}")

        _memory_quiz_questions[question_id] = q_data
        return q_data

    async def get_question(
        self,
        question_id: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    query = "SELECT * FROM quiz_questions WHERE id = $1"
                    params = [uuid.UUID(question_id) if len(question_id) == 36 else question_id]
                    if workspace_id:
                        query += " AND workspace_id = $2"
                        params.append(workspace_id)
                    row = await conn.fetchrow(query, *params)
                    if row:
                        d = dict(row)
                        if isinstance(d.get("options"), str):
                            d["options"] = json.loads(d["options"])
                        return d
            except Exception as e:
                logger.error(f"Error fetching quiz question from DB: {e}")

        q = _memory_quiz_questions.get(question_id)
        if q and (not workspace_id or q["workspace_id"] == workspace_id):
            return q
        return None

    async def list_questions_by_session(
        self,
        session_id: str,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    query = "SELECT * FROM quiz_questions WHERE quiz_session_id = $1"
                    params = [uuid.UUID(session_id) if len(session_id) == 36 else session_id]
                    if workspace_id:
                        query += " AND workspace_id = $2"
                        params.append(workspace_id)
                    query += " ORDER BY question_index ASC"
                    rows = await conn.fetch(query, *params)
                    result = []
                    for r in rows:
                        d = dict(r)
                        if isinstance(d.get("options"), str):
                            d["options"] = json.loads(d["options"])
                        result.append(d)
                    return result
            except Exception as e:
                logger.error(f"Error listing quiz questions from DB: {e}")

        matching = [
            q for q in _memory_quiz_questions.values() 
            if str(q["quiz_session_id"]) == str(session_id) and (not workspace_id or q["workspace_id"] == workspace_id)
        ]
        matching.sort(key=lambda x: x.get("question_index", 0))
        return matching

    async def create_attempt(
        self,
        quiz_session_id: str,
        question_id: str,
        workspace_id: str,
        user_id: str,
        selected_option: str,
        is_correct: bool,
        response_time_ms: int,
    ) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        att_data = {
            "id": attempt_id,
            "quiz_session_id": quiz_session_id,
            "question_id": question_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "selected_option": selected_option,
            "is_correct": is_correct,
            "response_time_ms": response_time_ms,
            "answered_at": now,
            "created_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO quiz_attempts
                        (id, quiz_session_id, question_id, workspace_id, user_id, selected_option, is_correct, response_time_ms, answered_at, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        uuid.UUID(attempt_id),
                        uuid.UUID(quiz_session_id) if len(quiz_session_id) == 36 else quiz_session_id,
                        uuid.UUID(question_id) if len(question_id) == 36 else question_id,
                        workspace_id,
                        user_id,
                        selected_option,
                        is_correct,
                        response_time_ms,
                        now,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error creating quiz attempt in DB: {e}")

        _memory_quiz_attempts[attempt_id] = att_data
        return att_data

    async def list_attempts_by_session(
        self,
        session_id: str,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    query = "SELECT * FROM quiz_attempts WHERE quiz_session_id = $1"
                    params = [uuid.UUID(session_id) if len(session_id) == 36 else session_id]
                    if workspace_id:
                        query += " AND workspace_id = $2"
                        params.append(workspace_id)
                    query += " ORDER BY answered_at ASC"
                    rows = await conn.fetch(query, *params)
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing quiz attempts from DB: {e}")

        matching = [
            a for a in _memory_quiz_attempts.values()
            if str(a["quiz_session_id"]) == str(session_id) and (not workspace_id or a["workspace_id"] == workspace_id)
        ]
        matching.sort(key=lambda x: x.get("answered_at") or datetime.min.replace(tzinfo=timezone.utc))
        return matching

    async def list_attempts_by_workspace(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM quiz_attempts 
                        WHERE workspace_id = $1 AND user_id = $2
                        ORDER BY answered_at ASC
                        """,
                        workspace_id,
                        user_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing workspace attempts from DB: {e}")

        matching = [
            a for a in _memory_quiz_attempts.values()
            if a["workspace_id"] == workspace_id and a.get("user_id", "default_user") == user_id
        ]
        matching.sort(key=lambda x: x.get("answered_at") or datetime.min.replace(tzinfo=timezone.utc))
        return matching


quiz_repo = QuizRepository()
