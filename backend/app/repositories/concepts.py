"""
Topic map storage: the concepts identified in each document of a workspace.

Each concept has a topic (chapter-level grouping), a short summary, the key facts a learner must
know and the source pages. Quiz questions and flashcards are generated per concept.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.db.connection import get_db_pool

logger = get_logger(__name__)

# In-memory storage when no database is configured (local development and tests)
_memory_concepts: Dict[str, Dict[str, Any]] = {}


def _row_to_concept(row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row)
    for key in ("key_points", "source_pages"):
        if isinstance(item.get(key), str):
            try:
                item[key] = json.loads(item[key])
            except ValueError:
                item[key] = []
        item[key] = item.get(key) or []
    return item


class ConceptRepository:
    async def replace_for_document(
        self,
        workspace_id: str,
        document_id: str,
        document_name: Optional[str],
        concepts: List[Dict[str, Any]],
        method: str = "ai",
    ) -> List[Dict[str, Any]]:
        """Stores a document's topic map, replacing any earlier one."""
        await self.delete_by_document(document_id)
        now = datetime.now(timezone.utc)
        saved: List[Dict[str, Any]] = []
        for position, c in enumerate(concepts):
            saved.append({
                "id": f"cpt_{uuid.uuid4().hex[:16]}",
                "workspace_id": workspace_id,
                "document_id": str(document_id),
                "document_name": document_name,
                "topic": (c.get("topic") or "General").replace("\x00", "")[:120],
                "concept": (c.get("concept") or "").replace("\x00", "")[:160],
                "summary": (c.get("summary") or "").replace("\x00", ""),
                "key_points": [str(p).replace("\x00", "") for p in (c.get("key_points") or [])],
                "source_pages": [int(p) for p in (c.get("source_pages") or []) if str(p).isdigit()],
                "position": position,
                "method": method,
                "created_at": now,
            })

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.executemany(
                        """
                        INSERT INTO workspace_concepts
                        (id, workspace_id, document_id, document_name, topic, concept, summary,
                         key_points, source_pages, position, method, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        """,
                        [
                            (
                                c["id"], c["workspace_id"], c["document_id"], c["document_name"], c["topic"],
                                c["concept"], c["summary"], json.dumps(c["key_points"]),
                                json.dumps(c["source_pages"]), c["position"], c["method"], c["created_at"],
                            )
                            for c in saved
                        ],
                    )
                return saved
            except Exception as e:
                logger.error(f"Error saving the topic map for document {document_id}: {e}")
                return saved

        for c in saved:
            _memory_concepts[c["id"]] = c
        return saved

    async def list_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM workspace_concepts
                        WHERE workspace_id = $1
                        ORDER BY created_at ASC, position ASC
                        """,
                        workspace_id,
                    )
                    return [_row_to_concept(dict(r)) for r in rows]
            except Exception as e:
                logger.error(f"Error listing the topic map of workspace {workspace_id}: {e}")
                return []

        items = [c for c in _memory_concepts.values() if c["workspace_id"] == workspace_id]
        items.sort(key=lambda c: (c["created_at"], c["position"]))
        return [dict(c) for c in items]

    async def list_document_ids(self, workspace_id: str) -> List[str]:
        """Documents that already have a topic map."""
        return sorted({str(c["document_id"]) for c in await self.list_by_workspace(workspace_id) if c.get("document_id")})

    async def delete_by_document(self, document_id: str) -> None:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("DELETE FROM workspace_concepts WHERE document_id = $1", str(document_id))
            except Exception as e:
                logger.error(f"Error deleting the topic map of document {document_id}: {e}")
            return
        for cid in [k for k, c in _memory_concepts.items() if str(c.get("document_id")) == str(document_id)]:
            _memory_concepts.pop(cid, None)


concept_repo = ConceptRepository()
