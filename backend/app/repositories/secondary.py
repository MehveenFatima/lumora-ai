import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool, check_presentation_mode_database_availability
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage tables for local/dev fallback
_memory_flashcards: Dict[str, List[Dict[str, Any]]] = {}
_memory_study_plans: Dict[str, Dict[str, Any]] = {}
_memory_activities: Dict[str, List[Dict[str, Any]]] = {}


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
                        return [dict(r) for r in rows]
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
                "created_at": now,
            }
            if pool:
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO flashcards (id, workspace_id, front, back, concept, source_document, source_page, interval_days, last_reviewed, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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


class StudyPlanRepository:
    async def get_by_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM study_plans WHERE workspace_id = $1", workspace_id
                    )
                    if row:
                        res = dict(row)
                        if isinstance(res.get("tasks"), str):
                            res["tasks"] = json.loads(res["tasks"])
                        return res
            except Exception as e:
                logger.error(f"Error querying study plan for {workspace_id}: {e}")

        return _memory_study_plans.get(workspace_id)

    async def save_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        ws_id = plan["workspace_id"]
        pool = await get_db_pool()
        check_presentation_mode_database_availability(pool)

        now = datetime.now(timezone.utc)
        tasks_json = json.dumps(plan.get("tasks", []))

        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO study_plans (workspace_id, daily_target_minutes, today_completed_minutes, weekly_target_minutes, week_completed_minutes, tasks, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                        ON CONFLICT (workspace_id) DO UPDATE SET
                            daily_target_minutes = EXCLUDED.daily_target_minutes,
                            today_completed_minutes = EXCLUDED.today_completed_minutes,
                            weekly_target_minutes = EXCLUDED.weekly_target_minutes,
                            week_completed_minutes = EXCLUDED.week_completed_minutes,
                            tasks = EXCLUDED.tasks,
                            updated_at = EXCLUDED.updated_at
                        """,
                        ws_id,
                        plan.get("daily_target_minutes", 45),
                        plan.get("today_completed_minutes", 0),
                        plan.get("weekly_target_minutes", 225),
                        plan.get("week_completed_minutes", 0),
                        tasks_json,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error saving study plan for {ws_id}: {e}")

        _memory_study_plans[ws_id] = {**plan, "updated_at": now}
        return _memory_study_plans[ws_id]


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
