import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timezone
from backend.app.db.connection import get_db_pool, check_presentation_mode_database_availability
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage tables for local/dev fallback
_memory_flashcards: Dict[str, List[Dict[str, Any]]] = {}
_memory_study_plans: Dict[str, Dict[str, Any]] = {}
_memory_activities: Dict[str, List[Dict[str, Any]]] = {}


def _card_row(row: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(row.get("embedding"), str):
        try:
            row["embedding"] = json.loads(row["embedding"])
        except ValueError:
            row["embedding"] = None
    return row


class FlashcardRepository:
    async def list_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM flashcards WHERE workspace_id = $1 ORDER BY created_at ASC",
                        workspace_id,
                    )
                    if rows:
                        return [_card_row(dict(r)) for r in rows]
            except Exception as e:
                logger.error(f"Error querying flashcards for workspace {workspace_id}: {e}")

        return _memory_flashcards.get(workspace_id, [])

    async def save_flashcards(self, workspace_id: str, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        saved = []
        now = datetime.now(timezone.utc)
        for c in cards:
            cid = c.get("id") or f"fc_{uuid.uuid4().hex[:10]}"
            item = {
                "id": cid,
                "workspace_id": workspace_id,
                "front": c["front"].replace("\x00", "") if isinstance(c.get("front"), str) else "",
                "back": c["back"].replace("\x00", "") if isinstance(c.get("back"), str) else "",
                "concept": c.get("concept", "General").replace("\x00", "") if isinstance(c.get("concept"), str) else "General",
                "source_document": c.get("source_document", "Workspace Notes"),
                "source_page": c.get("source_page", 1),
                "interval_days": c.get("interval_days", 1),
                "last_reviewed": c.get("last_reviewed"),
                "document_id": c.get("document_id"),
                "concept_id": c.get("concept_id"),
                "generator": c.get("generator"),
                "embedding": c.get("embedding"),
                "created_at": now,
            }
            if pool:
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO flashcards (id, workspace_id, front, back, concept, source_document, source_page, interval_days, last_reviewed, created_at,
                                                    document_id, concept_id, generator, embedding)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                            ON CONFLICT (id) DO UPDATE SET
                                front = EXCLUDED.front,
                                back = EXCLUDED.back,
                                interval_days = EXCLUDED.interval_days,
                                last_reviewed = EXCLUDED.last_reviewed
                            """,
                            item["id"],
                            item["workspace_id"],
                            item["front"],
                            item["back"],
                            item["concept"],
                            item["source_document"],
                            item["source_page"],
                            item["interval_days"],
                            item["last_reviewed"],
                            item["created_at"],
                            item["document_id"],
                            item["concept_id"],
                            item["generator"],
                            json.dumps(item["embedding"]) if item["embedding"] else None,
                        )
                except Exception as e:
                    logger.error(f"Error saving flashcard {cid}: {e}")
            saved.append(item)

        if workspace_id not in _memory_flashcards:
            _memory_flashcards[workspace_id] = []
        # Replace or append
        existing_ids = {c["id"] for c in saved}
        _memory_flashcards[workspace_id] = [
            c for c in _memory_flashcards[workspace_id] if c["id"] not in existing_ids
        ] + saved

        return saved

    save_deck = save_flashcards

    async def delete_by_workspace(self, workspace_id: str) -> None:
        """Removes every flashcard in a workspace (used when a deck is rebuilt)."""
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)
        if pool:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM flashcards WHERE workspace_id = $1", workspace_id)
        _memory_flashcards.pop(workspace_id, None)

    async def delete_ids(self, workspace_id: str, card_ids: List[str]) -> None:
        """Removes the given cards (used to retire an old deck once its replacement is saved)."""
        if not card_ids:
            return
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM flashcards WHERE workspace_id = $1 AND id = ANY($2::text[])",
                        workspace_id, list(card_ids),
                    )
            except Exception as e:
                logger.error(f"Error deleting old flashcards of workspace {workspace_id}: {e}")
        ids = set(card_ids)
        if workspace_id in _memory_flashcards:
            _memory_flashcards[workspace_id] = [c for c in _memory_flashcards[workspace_id] if c["id"] not in ids]

    async def delete_by_document(self, workspace_id: str, document_id: str) -> None:
        """Removes the cards written from a deleted document."""
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM flashcards WHERE workspace_id = $1 AND document_id = $2",
                        workspace_id, str(document_id),
                    )
            except Exception as e:
                logger.error(f"Error deleting flashcards of document {document_id}: {e}")
        if workspace_id in _memory_flashcards:
            _memory_flashcards[workspace_id] = [
                c for c in _memory_flashcards[workspace_id] if str(c.get("document_id")) != str(document_id)
            ]

    async def record_review(
        self,
        workspace_id: str,
        card_id: str,
        rating: str,
        repetitions: int,
        interval_days: int,
        ease_factor: float,
        due_date,
    ) -> Optional[Dict[str, Any]]:
        """Persists one review's SM-2 schedule. Returns the updated card, or None if it doesn't exist."""
        today = datetime.now(timezone.utc).date()
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE flashcards
                    SET repetitions = $3, interval_days = $4, ease_factor = $5, due_date = $6,
                        last_rating = $7, last_reviewed = $8, review_count = review_count + 1
                    WHERE id = $1 AND workspace_id = $2
                    RETURNING *
                    """,
                    card_id, workspace_id, repetitions, interval_days, ease_factor, due_date, rating, today,
                )
                return dict(row) if row else None

        for card in _memory_flashcards.get(workspace_id, []):
            if card["id"] == card_id:
                card.update(
                    repetitions=repetitions,
                    interval_days=interval_days,
                    ease_factor=ease_factor,
                    due_date=due_date,
                    last_rating=rating,
                    last_reviewed=today,
                    review_count=int(card.get("review_count") or 0) + 1,
                )
                return card
        return None


_PLAN_JSON_FIELDS = ("tasks", "completions", "snapshot", "previous_snapshot")


def _plan_row(row: Dict[str, Any]) -> Dict[str, Any]:
    for key in _PLAN_JSON_FIELDS:
        if isinstance(row.get(key), str):
            try:
                row[key] = json.loads(row[key])
            except ValueError:
                row[key] = None
    row["completions"] = row.get("completions") or []
    return row


class StudyPlanRepository:
    """One row per workspace: today's frozen task list, every completion with its date, and the
    latest full schedule (``tasks``) for reference."""

    async def get_by_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM study_plans WHERE workspace_id = $1", workspace_id
                    )
                    return _plan_row(dict(row)) if row else None
            except Exception as e:
                logger.error(f"Error querying study plan for {workspace_id}: {e}")

        plan = _memory_study_plans.get(workspace_id)
        return _plan_row(json.loads(json.dumps(plan, default=str))) if plan else None

    async def save_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        ws_id = plan["workspace_id"]
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        now = datetime.now(timezone.utc)
        snapshot_date = plan.get("snapshot_date")
        if isinstance(snapshot_date, str):
            snapshot_date = date.fromisoformat(snapshot_date[:10])
        snapshot_at = plan.get("snapshot_at")
        if isinstance(snapshot_at, str):
            snapshot_at = datetime.fromisoformat(snapshot_at)

        def dump(value: Any) -> Optional[str]:
            return None if value is None else json.dumps(value, default=str)

        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO study_plans (
                            workspace_id, daily_target_minutes, today_completed_minutes, weekly_target_minutes,
                            week_completed_minutes, tasks, completions, snapshot, snapshot_date, snapshot_at,
                            previous_snapshot, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9, $10, $11::jsonb, $12)
                        ON CONFLICT (workspace_id) DO UPDATE SET
                            daily_target_minutes = EXCLUDED.daily_target_minutes,
                            today_completed_minutes = EXCLUDED.today_completed_minutes,
                            weekly_target_minutes = EXCLUDED.weekly_target_minutes,
                            week_completed_minutes = EXCLUDED.week_completed_minutes,
                            tasks = EXCLUDED.tasks,
                            completions = EXCLUDED.completions,
                            snapshot = EXCLUDED.snapshot,
                            snapshot_date = EXCLUDED.snapshot_date,
                            snapshot_at = EXCLUDED.snapshot_at,
                            previous_snapshot = EXCLUDED.previous_snapshot,
                            updated_at = EXCLUDED.updated_at
                        """,
                        ws_id,
                        plan.get("daily_target_minutes", 45),
                        plan.get("today_completed_minutes", 0),
                        plan.get("weekly_target_minutes", 315),
                        plan.get("week_completed_minutes", 0),
                        dump(plan.get("tasks") or []),
                        dump(plan.get("completions") or []),
                        dump(plan.get("snapshot")),
                        snapshot_date,
                        snapshot_at,
                        dump(plan.get("previous_snapshot")),
                        now,
                    )
            except Exception as e:
                logger.error(f"Error saving study plan for {ws_id}: {e}")

        stored = json.loads(json.dumps({**plan, "updated_at": now}, default=str))
        _memory_study_plans[ws_id] = stored
        return _plan_row(json.loads(json.dumps(stored)))


class ActivityRepository:
    async def list_by_workspace(self, workspace_id: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        if pool:
            try:
                async with pool.acquire() as conn:
                    if workspace_id:
                        rows = await conn.fetch(
                            "SELECT * FROM activity_events WHERE workspace_id = $1 ORDER BY created_at DESC LIMIT $2",
                            workspace_id,
                            limit,
                        )
                    else:
                        rows = await conn.fetch(
                            "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT $1",
                            limit,
                        )
                    if rows:
                        return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing activities: {e}")

        if workspace_id:
            return _memory_activities.get(workspace_id, [])[:limit]
        
        all_acts = []
        for acts in _memory_activities.values():
            all_acts.extend(acts)
        all_acts.sort(key=lambda x: x.get("created_at", datetime.now(timezone.utc)), reverse=True)
        return all_acts[:limit]

    async def add_activity(
        self,
        workspace_id: str,
        event_type: str,
        title: str,
        description: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        aid = f"act_{int(now.timestamp() * 1000)}"
        ts_str = timestamp or now.isoformat()
        item = {
            "id": aid,
            "workspace_id": workspace_id,
            "event_type": event_type,
            "title": title,
            "description": description,
            "timestamp": ts_str,
            "created_at": now,
        }

        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO activity_events (id, workspace_id, event_type, title, description, timestamp, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        aid,
                        workspace_id,
                        event_type,
                        title,
                        description,
                        ts_str,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error inserting activity {aid}: {e}")

        if workspace_id not in _memory_activities:
            _memory_activities[workspace_id] = []
        _memory_activities[workspace_id].insert(0, item)
        return item


flashcard_repo = FlashcardRepository()
study_plan_repo = StudyPlanRepository()
activity_repo = ActivityRepository()
