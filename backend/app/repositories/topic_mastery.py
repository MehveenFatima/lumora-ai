"""
LumoraAI - Topic Mastery and Mastery Snapshots Repository
Persistence layer for learner topic mastery and historical mastery snapshots.
Supports PostgreSQL with thread-safe in-memory fallback.
"""
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage fallbacks
_memory_topic_mastery: Dict[str, Dict[str, Any]] = {}
_memory_mastery_snapshots: Dict[str, List[Dict[str, Any]]] = {}


class TopicMasteryRepository:
    async def upsert_topic_mastery(
        self,
        workspace_id: str,
        topic: str,
        mastery_probability: float,
        confidence_level: str,
        mastery_status: str,
        trend: str,
        concept_count: int,
        assessed_concept_count: int,
        coverage_ratio: float,
        attempt_count: int,
        correct_count: int,
        recent_accuracy: float,
        average_response_time_ms: int,
        gap_priority: float,
        last_assessed_at: Optional[datetime] = None,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        key = f"{workspace_id}:{user_id}:{topic}"
        now = datetime.now(timezone.utc)
        assessed_at = last_assessed_at or now

        existing = _memory_topic_mastery.get(key, {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "topic": topic,
            "created_at": now,
        })

        record = {
            "id": existing.get("id") or str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "topic": topic,
            "mastery_probability": round(float(mastery_probability), 4),
            "confidence_level": confidence_level,
            "mastery_status": mastery_status,
            "trend": trend,
            "concept_count": int(concept_count),
            "assessed_concept_count": int(assessed_concept_count),
            "coverage_ratio": round(float(coverage_ratio), 4),
            "attempt_count": int(attempt_count),
            "correct_count": int(correct_count),
            "recent_accuracy": round(float(recent_accuracy), 4),
            "average_response_time_ms": int(average_response_time_ms),
            "gap_priority": round(float(gap_priority), 4),
            "last_assessed_at": assessed_at,
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }
        _memory_topic_mastery[key] = record

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO learner_topic_mastery (
                            workspace_id, user_id, topic, mastery_probability, confidence_level,
                            mastery_status, trend, concept_count, assessed_concept_count,
                            coverage_ratio, attempt_count, correct_count, recent_accuracy,
                            average_response_time_ms, gap_priority, last_assessed_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                        ON CONFLICT (workspace_id, user_id, topic)
                        DO UPDATE SET
                            mastery_probability = EXCLUDED.mastery_probability,
                            confidence_level = EXCLUDED.confidence_level,
                            mastery_status = EXCLUDED.mastery_status,
                            trend = EXCLUDED.trend,
                            concept_count = EXCLUDED.concept_count,
                            assessed_concept_count = EXCLUDED.assessed_concept_count,
                            coverage_ratio = EXCLUDED.coverage_ratio,
                            attempt_count = EXCLUDED.attempt_count,
                            correct_count = EXCLUDED.correct_count,
                            recent_accuracy = EXCLUDED.recent_accuracy,
                            average_response_time_ms = EXCLUDED.average_response_time_ms,
                            gap_priority = EXCLUDED.gap_priority,
                            last_assessed_at = EXCLUDED.last_assessed_at,
                            updated_at = EXCLUDED.updated_at
                        """,
                        workspace_id,
                        user_id,
                        topic,
                        record["mastery_probability"],
                        confidence_level,
                        mastery_status,
                        trend,
                        record["concept_count"],
                        record["assessed_concept_count"],
                        record["coverage_ratio"],
                        record["attempt_count"],
                        record["correct_count"],
                        record["recent_accuracy"],
                        record["average_response_time_ms"],
                        record["gap_priority"],
                        assessed_at,
                        now,
                    )
            except Exception as e:
                logger.warning(f"Failed to upsert learner_topic_mastery in PostgreSQL: {e}")

        return record

    async def get_topic_mastery(
        self,
        workspace_id: str,
        topic: str,
        user_id: str = "default_user",
    ) -> Optional[Dict[str, Any]]:
        key = f"{workspace_id}:{user_id}:{topic}"
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM learner_topic_mastery WHERE workspace_id = $1 AND user_id = $2 AND topic = $3",
                        workspace_id,
                        user_id,
                        topic,
                    )
                    if row:
                        return dict(row)
            except Exception as e:
                logger.warning(f"PostgreSQL query error in get_topic_mastery: {e}")
        return _memory_topic_mastery.get(key)

    async def list_topic_mastery(
        self,
        workspace_id: str,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM learner_topic_mastery WHERE workspace_id = $1 AND user_id = $2 ORDER BY topic ASC",
                        workspace_id,
                        user_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in list_topic_mastery: {e}")

        prefix = f"{workspace_id}:{user_id}:"
        res = [v for k, v in _memory_topic_mastery.items() if k.startswith(prefix)]
        return sorted(res, key=lambda x: x.get("topic", ""))

    async def record_snapshot(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        mastery_probability: float,
        confidence_level: str,
        gap_priority: float = 0.0,
        attempt_count: int = 0,
        snapshot_event: str = "attempt",
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        key = f"{workspace_id}:{user_id}:{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        record = {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "mastery_probability": round(float(mastery_probability), 4),
            "confidence_level": confidence_level,
            "gap_priority": round(float(gap_priority), 4),
            "attempt_count": int(attempt_count),
            "snapshot_event": snapshot_event,
            "created_at": now,
        }

        if key not in _memory_mastery_snapshots:
            _memory_mastery_snapshots[key] = []
        _memory_mastery_snapshots[key].append(record)

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO learner_mastery_snapshots (
                            workspace_id, user_id, entity_type, entity_id,
                            mastery_probability, confidence_level, gap_priority,
                            attempt_count, snapshot_event, created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        workspace_id,
                        user_id,
                        entity_type,
                        entity_id,
                        record["mastery_probability"],
                        confidence_level,
                        record["gap_priority"],
                        record["attempt_count"],
                        snapshot_event,
                        now,
                    )
            except Exception as e:
                logger.warning(f"Failed to record learner_mastery_snapshot in PostgreSQL: {e}")

        return record

    async def get_recent_snapshots(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        limit: int = 5,
        user_id: str = "default_user",
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM learner_mastery_snapshots
                        WHERE workspace_id = $1 AND user_id = $2 AND entity_type = $3 AND entity_id = $4
                        ORDER BY created_at DESC
                        LIMIT $5
                        """,
                        workspace_id,
                        user_id,
                        entity_type,
                        entity_id,
                        limit,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning(f"PostgreSQL query error in get_recent_snapshots: {e}")

        key = f"{workspace_id}:{user_id}:{entity_type}:{entity_id}"
        items = _memory_mastery_snapshots.get(key, [])
        return sorted(items, key=lambda x: x["created_at"], reverse=True)[:limit]


topic_mastery_repo = TopicMasteryRepository()
