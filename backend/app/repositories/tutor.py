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


class TutorRepository:
    async def get_or_create_conversation(
        self, workspace_id: str, conversation_id: Optional[str] = None
    ) -> str:
        now = datetime.now(timezone.utc)
        if conversation_id and conversation_id in _memory_conversations:
            return conversation_id

        conv_id = conversation_id or str(uuid.uuid4())
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
                        uuid.UUID(conv_id),
                        workspace_id,
                        conv_data["title"],
                        now,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error creating conversation: {e}")

        _memory_conversations[conv_id] = conv_data
        return conv_id

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
                        uuid.UUID(msg_id),
                        uuid.UUID(conversation_id),
                        workspace_id,
                        role,
                        content,
                        json.dumps(citations or []),
                        json.dumps(retrieval_metadata or {}),
                        now,
                    )
            except Exception as e:
                logger.error(f"Error inserting tutor message: {e}")

        _memory_messages.append(msg_data)
        return msg_data

    async def get_recent_messages(
        self, conversation_id: str, limit: int = 8
    ) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, role, content, citations, created_at
                        FROM tutor_messages
                        WHERE conversation_id = $1
                        ORDER BY created_at ASC
                        LIMIT $2
                        """,
                        uuid.UUID(conversation_id),
                        limit,
                    )
                    if rows:
                        return [
                            {
                                "id": str(r["id"]),
                                "role": r["role"],
                                "content": r["content"],
                                "citations": r["citations"] if isinstance(r["citations"], list) else json.loads(r["citations"] or "[]"),
                                "created_at": r["created_at"],
                            }
                            for r in rows
                        ]
            except Exception as e:
                logger.error(f"Error fetching conversation messages: {e}")

        msgs = [
            m for m in _memory_messages if m["conversation_id"] == conversation_id
        ]
        return msgs[-limit:]


tutor_repo = TutorRepository()
