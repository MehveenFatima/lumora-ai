"""In-app notifications, stored per user. A dedupe_key keeps one event from being stored twice."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.db.connection import get_db_pool

logger = get_logger(__name__)

_memory_notifications: List[Dict[str, Any]] = []


class NotificationRepository:
    async def add(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        workspace_id: Optional[str] = None,
        link: Optional[str] = None,
        dedupe_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Stores a notification; returns None if one with the same dedupe_key already exists."""
        item = {
            "id": f"ntf_{uuid.uuid4().hex}",
            "user_id": user_id,
            "workspace_id": workspace_id,
            "type": type,
            "title": title[:200],
            "message": message[:500],
            "link": link,
            "dedupe_key": dedupe_key,
            "read_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO notifications (id, user_id, workspace_id, type, title, message, link, dedupe_key, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
                        RETURNING *
                        """,
                        item["id"], user_id, workspace_id, item["type"], item["title"], item["message"],
                        link, dedupe_key, item["created_at"],
                    )
                    return dict(row) if row else None
            except Exception as e:
                # Notifications must never break the action that triggered them
                logger.warning(f"Could not store notification for {user_id}: {e}")
                return None

        if dedupe_key and any(n["user_id"] == user_id and n["dedupe_key"] == dedupe_key for n in _memory_notifications):
            return None
        _memory_notifications.append(item)
        return item

    async def list_for_user(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                    user_id, limit,
                )
                return [dict(r) for r in rows]
        mine = [n for n in _memory_notifications if n["user_id"] == user_id]
        return sorted(mine, key=lambda n: n["created_at"], reverse=True)[:limit]

    async def unread_count(self, user_id: str) -> int:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                return int(await conn.fetchval(
                    "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL", user_id
                ) or 0)
        return sum(1 for n in _memory_notifications if n["user_id"] == user_id and n["read_at"] is None)

    async def mark_read(self, user_id: str, notification_id: str) -> bool:
        now = datetime.now(timezone.utc)
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE notifications SET read_at = COALESCE(read_at, $3) WHERE id = $1 AND user_id = $2",
                    notification_id, user_id, now,
                )
                return result.endswith(" 1")
        for n in _memory_notifications:
            if n["id"] == notification_id and n["user_id"] == user_id:
                n["read_at"] = n["read_at"] or now
                return True
        return False

    async def mark_all_read(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE notifications SET read_at = $2 WHERE user_id = $1 AND read_at IS NULL", user_id, now
                )
            return
        for n in _memory_notifications:
            if n["user_id"] == user_id and n["read_at"] is None:
                n["read_at"] = now


notification_repo = NotificationRepository()
