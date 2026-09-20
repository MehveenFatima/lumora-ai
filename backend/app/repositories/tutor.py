from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage fallback
_memory_conversations: Dict[str, Dict[str, Any]] = {}
_memory_messages: List[Dict[str, Any]] = []


def _safe_uuid(val: Optional[str]) -> uuid.UUID:
    if not val:
        return uuid.uuid4()
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


class TutorRepository:
    async def get_or_create_conversation(
        self, workspace_id: str, conversation_id: Optional[str] = None
    ) -> str:
        now = datetime.now(timezone.utc)
        if conversation_id and conversation_id in _memory_conversations:
            return conversation_id

        conv_id = conversation_id or str(uuid.uuid4())
        db_conv_uuid = _safe_uuid(conv_id)
        conv_data = {
            "id": conv_id,
            "workspace_id": workspace_id,
            "title": "Tutor Session",
            "created_at": now,
            "updated_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO tutor_conversations (id, workspace_id, title, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        db_conv_uuid,
                        workspace_id,
                        conv_data["title"],
                        now,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error creating conversation: {e}")

        _memory_conversations[conv_id] = conv_data
        return conv_id

    async def get_latest_conversation_id(self, workspace_id: str) -> Optional[str]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT id FROM tutor_conversations
                        WHERE workspace_id = $1
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1
                        """,
                        workspace_id,
                    )
                    if row:
                        return str(row["id"])
            except Exception as e:
                logger.error(f"Error fetching latest conversation: {e}")

        workspace_convs = [
            c for c in _memory_conversations.values() if c.get("workspace_id") == workspace_id
        ]
        if workspace_convs:
            workspace_convs.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
            return workspace_convs[0]["id"]
        return None

    async def add_message(
        self,
        conversation_id: str,
        workspace_id: str,
        role: str,
        content: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        retrieval_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        db_msg_uuid = _safe_uuid(msg_id)
        db_conv_uuid = _safe_uuid(conversation_id)
        now = datetime.now(timezone.utc)
        msg_data = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "role": role,
            "content": content,
            "citations": citations or [],
            "retrieval_metadata": retrieval_metadata or {},
            "created_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO tutor_messages (id, conversation_id, workspace_id, role, content, citations, retrieval_metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        db_msg_uuid,
                        db_conv_uuid,
                        workspace_id,
                        role,
                        content,
                        json.dumps(citations or []),
                        json.dumps(retrieval_metadata or {}),
                        now,
                    )
                    await conn.execute(
                        """
                        UPDATE tutor_conversations
                        SET updated_at = $2
                        WHERE id = $1
                        """,
                        db_conv_uuid,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error inserting tutor message: {e}")

        if conversation_id in _memory_conversations:
            _memory_conversations[conversation_id]["updated_at"] = now
        _memory_messages.append(msg_data)
        return msg_data

    async def get_recent_messages(
        self, conversation_id: str, limit: int = 8
    ) -> List[Dict[str, Any]]:
        db_conv_uuid = _safe_uuid(conversation_id)
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, role, content, citations, created_at
                        FROM tutor_messages
                        WHERE conversation_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                        """,
                        db_conv_uuid,
                        limit,
                    )
                    if rows:
                        chrono_rows = list(reversed(rows))
                        return [
                            {
                                "id": str(r["id"]),
                                "role": r["role"],
                                "content": r["content"],
                                "citations": r["citations"] if isinstance(r["citations"], list) else json.loads(r["citations"] or "[]"),
                                "created_at": r["created_at"],
                            }
                            for r in chrono_rows
                        ]
            except Exception as e:
                logger.error(f"Error fetching conversation messages: {e}")

        msgs = [
            m for m in _memory_messages if m["conversation_id"] == conversation_id
        ]
        return msgs[-limit:]


tutor_repo = TutorRepository()
