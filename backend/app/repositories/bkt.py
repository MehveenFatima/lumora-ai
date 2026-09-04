"""
LumoraAI - BKT and Knowledge Gap Repository
Persistence layer for learner concept mastery, knowledge gap rankings, and question fingerprints.
"""
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage fallbacks
_memory_concept_mastery: Dict[str, Dict[str, Any]] = {}
_memory_knowledge_gaps: Dict[str, Dict[str, Any]] = {}
_memory_question_fingerprints: Dict[str, List[str]] = {}


class BKTRepository:
    async def upsert_concept_mastery(
        self,
        workspace_id: str,
        topic: str,
        concept: str,
        p_mastery: float,
        is_correct: bool,
        response_time_ms: int = 0,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        key = f"{workspace_id}:{user_id}:{concept}"
        now = datetime.now(timezone.utc)

        existing = _memory_concept_mastery.get(key, {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "topic": topic,
            "concept": concept,
            "p_mastery": 0.30,
            "attempts_count": 0,
            "correct_count": 0,
            "last_response_time_ms": 0,
            "last_practiced_at": now,
        })

        new_attempts = existing.get("attempts_count", 0) + 1
        new_correct = existing.get("correct_count", 0) + (1 if is_correct else 0)
        new_incorrect = existing.get("incorrect_count", 0) + (0 if is_correct else 1)
        recent_acc = round(new_correct / new_attempts, 4) if new_attempts > 0 else 0.0
        repeated_err = (existing.get("repeated_error_count", 0) + 1) if not is_correct else 0
        prev_avg_time = existing.get("average_response_time_ms", 0)
        prev_attempts = existing.get("attempts_count", 0)
        avg_time = int((prev_avg_time * prev_attempts + response_time_ms) / new_attempts) if new_attempts > 0 else response_time_ms

        # Confidence heuristic
        if new_attempts < 3:
            conf_level = "low"
        elif new_attempts < 8:
            conf_level = "moderate"
        else:
            conf_level = "high"

        # Status
        if conf_level == "low":
            m_status = "low_evidence" if p_mastery >= 0.80 else "developing"
        elif p_mastery >= 0.80:
            m_status = "strong"
        elif p_mastery >= 0.60:
            m_status = "developing"
        elif p_mastery >= 0.40:
            m_status = "needs_review"
        else:
            m_status = "critical_gap"

        # Trend
        prev_pm = existing.get("p_mastery", 0.30)
        delta = p_mastery - prev_pm
        if prev_attempts < 1:
            c_trend = "insufficient_data"
        elif delta >= 0.03:
            c_trend = "improving"
        elif delta <= -0.03:
            c_trend = "declining"
        else:
            c_trend = "stable"

        record = {
            "id": existing.get("id") or str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "topic": topic,
            "concept": concept,
            "p_mastery": round(float(p_mastery), 4),
            "bkt_version": "1.0",
            "attempts_count": new_attempts,
            "correct_count": new_correct,
            "incorrect_count": new_incorrect,
            "recent_accuracy": recent_acc,
            "average_response_time_ms": avg_time,
            "repeated_error_count": repeated_err,
            "first_attempt_at": existing.get("first_attempt_at") or now,
            "last_attempt_at": now,
            "last_response_time_ms": response_time_ms,
            "last_practiced_at": now,
            "mastery_status": m_status,
            "confidence_level": conf_level,
            "trend": c_trend,
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }
        _memory_concept_mastery[key] = record

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO learner_concept_mastery (
                            workspace_id, user_id, topic, concept, p_mastery,
                            bkt_version, attempts_count, correct_count, incorrect_count,
                            recent_accuracy, average_response_time_ms, repeated_error_count,
                            first_attempt_at, last_attempt_at, last_response_time_ms,
                            last_practiced_at, mastery_status, confidence_level, trend, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                        ON CONFLICT (workspace_id, user_id, concept)
                        DO UPDATE SET
                            topic = EXCLUDED.topic,
                            p_mastery = EXCLUDED.p_mastery,
                            bkt_version = EXCLUDED.bkt_version,
                            attempts_count = EXCLUDED.attempts_count,
                            correct_count = EXCLUDED.correct_count,
                            incorrect_count = EXCLUDED.incorrect_count,
                            recent_accuracy = EXCLUDED.recent_accuracy,
                            average_response_time_ms = EXCLUDED.average_response_time_ms,
                            repeated_error_count = EXCLUDED.repeated_error_count,
                            last_attempt_at = EXCLUDED.last_attempt_at,
                            last_response_time_ms = EXCLUDED.last_response_time_ms,
                            last_practiced_at = EXCLUDED.last_practiced_at,
                            mastery_status = EXCLUDED.mastery_status,
                            confidence_level = EXCLUDED.confidence_level,
                            trend = EXCLUDED.trend,
                            updated_at = EXCLUDED.updated_at
                        """,
                        workspace_id,
                        user_id,
                        topic,
                        concept,
                        record["p_mastery"],
                        "1.0",
                        new_attempts,
                        new_correct,
                        new_incorrect,
                        recent_acc,
                        avg_time,
                        repeated_err,
                        record["first_attempt_at"],
                        now,
                        response_time_ms,
                        now,
                        m_status,
                        conf_level,
                        c_trend,
                        now,
                    )
            except Exception as e:
                logger.warning(f"Failed to upsert learner_concept_mastery in PostgreSQL: {e}")

        return record

    async def get_concept_mastery(
        self,
        workspace_id: str,
        concept: str,
        user_id: str = "default_user",
    ) -> Optional[Dict[str, Any]]:
        key = f"{workspace_id}:{user_id}:{concept}"
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM learner_concept_mastery WHERE workspace_id = $1 AND user_id = $2 AND concept = $3",
                        workspace_id,
                        user_id,
                        concept,
                    )
                    if row:
                        return dict(row)
            except Exception as e:
                logger.warning(f"PostgreSQL query error in get_concept_mastery: {e}")
        return _memory_concept_mastery.get(key)

    async def list_concept_mastery(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM learner_concept_mastery WHERE workspace_id = $1 AND user_id = $2 ORDER BY updated_at DESC",
                        workspace_id,
                        user_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in list_concept_mastery: {e}")

        prefix = f"{workspace_id}:{user_id}:"
        return [v for k, v in _memory_concept_mastery.items() if k.startswith(prefix)]

    async def upsert_knowledge_gap(
        self,
        workspace_id: str,
        topic: str,
        concept: str,
        gap_priority: float,
        gap_status: str,
        contributing_signals: Dict[str, Any],
        recommended_action: str = "targeted_practice",
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        key = f"{workspace_id}:{user_id}:{concept}"
        now = datetime.now(timezone.utc)
        record = {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "topic": topic,
            "concept": concept,
            "gap_priority": gap_priority,
            "gap_status": gap_status,
            "contributing_signals": contributing_signals,
            "recommended_action": recommended_action,
            "created_at": now,
            "updated_at": now,
        }
        _memory_knowledge_gaps[key] = record

        pool = await get_db_pool()
        if pool:
            try:
                import json
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO learner_knowledge_gaps
                        (workspace_id, user_id, topic, concept, gap_priority, gap_status, contributing_signals, recommended_action, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (workspace_id, user_id, concept)
                        DO UPDATE SET
                            topic = EXCLUDED.topic,
                            gap_priority = EXCLUDED.gap_priority,
                            gap_status = EXCLUDED.gap_status,
                            contributing_signals = EXCLUDED.contributing_signals,
                            recommended_action = EXCLUDED.recommended_action,
                            updated_at = EXCLUDED.updated_at
                        """,
                        workspace_id,
                        user_id,
                        topic,
                        concept,
                        gap_priority,
                        gap_status,
                        json.dumps(contributing_signals),
                        recommended_action,
                        now,
                    )
            except Exception as e:
                logger.warning(f"Failed to upsert learner_knowledge_gaps in PostgreSQL: {e}")

        return record

    async def list_knowledge_gaps(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM learner_knowledge_gaps WHERE workspace_id = $1 AND user_id = $2 ORDER BY gap_priority DESC",
                        workspace_id,
                        user_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in list_knowledge_gaps: {e}")

        prefix = f"{workspace_id}:{user_id}:"
        res = [v for k, v in _memory_knowledge_gaps.items() if k.startswith(prefix)]
        return sorted(res, key=lambda x: x.get("gap_priority", 0.0), reverse=True)

    async def record_fingerprint(
        self,
        workspace_id: str,
        quiz_session_id: str,
        question_id: str,
        fingerprint: str,
    ) -> None:
        session_key = str(quiz_session_id)
        if session_key not in _memory_question_fingerprints:
            _memory_question_fingerprints[session_key] = []
        if fingerprint not in _memory_question_fingerprints[session_key]:
            _memory_question_fingerprints[session_key].append(fingerprint)

        # Also store workspace-wide
        ws_key = f"ws:{workspace_id}"
        if ws_key not in _memory_question_fingerprints:
            _memory_question_fingerprints[ws_key] = []
        if fingerprint not in _memory_question_fingerprints[ws_key]:
            _memory_question_fingerprints[ws_key].append(fingerprint)

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO quiz_question_fingerprints
                        (workspace_id, quiz_session_id, question_id, fingerprint)
                        VALUES ($1, $2, $3, $4)
                        """,
                        workspace_id,
                        uuid.UUID(quiz_session_id),
                        uuid.UUID(question_id),
                        fingerprint,
                    )
            except Exception as e:
                logger.warning(f"Failed to record quiz_question_fingerprint in PostgreSQL: {e}")

    async def list_session_fingerprints(
        self,
        workspace_id: str,
        quiz_session_id: str,
    ) -> List[str]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT fingerprint FROM quiz_question_fingerprints WHERE workspace_id = $1 AND quiz_session_id = $2",
                        workspace_id,
                        uuid.UUID(quiz_session_id),
                    )
                    return [r["fingerprint"] for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in list_session_fingerprints: {e}")

        return list(_memory_question_fingerprints.get(str(quiz_session_id), []))

    async def list_workspace_fingerprints(
        self,
        workspace_id: str,
    ) -> List[str]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT DISTINCT fingerprint FROM quiz_question_fingerprints WHERE workspace_id = $1",
                        workspace_id,
                    )
                    return [r["fingerprint"] for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in list_workspace_fingerprints: {e}")

        return list(_memory_question_fingerprints.get(f"ws:{workspace_id}", []))


bkt_repo = BKTRepository()
