from typing import Optional, Dict, Any, List
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage fallback for local execution & testing
_memory_workspaces: Dict[str, Dict[str, Any]] = {
    "dsa": {
        "id": "dsa",
        "name": "Data Structures & Algorithms",
        "goal": "Placement Prep 2026",
        "level": "intermediate",
        "description": "Master fundamental and advanced algorithmic problem solving.",
        "overall_mastery": 74,
        "mastery_delta": 5,
        "status": "on_track",
        "document_count": 0,
    },
    "os": {
        "id": "os",
        "name": "Operating Systems",
        "goal": "Semester 5 Core Prep",
        "level": "intermediate",
        "description": "Concurrency, virtual memory management, and file systems.",
        "overall_mastery": 64,
        "mastery_delta": 3,
        "status": "on_track",
        "document_count": 0,
    },
    "ml": {
        "id": "ml",
        "name": "Machine Learning & AI",
        "goal": "Certification Track",
        "level": "advanced",
        "description": "Statistical modeling, deep learning architectures, and transformers.",
        "overall_mastery": 57,
        "mastery_delta": 7,
        "status": "active",
        "document_count": 0,
    },
    "aws": {
        "id": "aws",
        "name": "AWS Solutions Architect",
        "goal": "SAA-C03 Certification",
        "level": "beginner",
        "description": "Cloud architecture, high availability, VPC, and IAM policies.",
        "overall_mastery": 48,
        "mastery_delta": 4,
        "status": "active",
        "document_count": 0,
    },
}


class WorkspaceRepository:
    async def get_by_id(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM workspaces WHERE id = $1", workspace_id
                )
                if row:
                    return dict(row)
        return _memory_workspaces.get(workspace_id)

    async def list_all(self) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM workspaces ORDER BY name ASC")
                if rows:
                    return [dict(r) for r in rows]
        return list(_memory_workspaces.values())

    async def increment_doc_count(self, workspace_id: str, delta: int = 1) -> None:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE workspaces SET document_count = GREATEST(0, document_count + $2) WHERE id = $1",
                    workspace_id,
                    delta,
                )
        if workspace_id in _memory_workspaces:
            _memory_workspaces[workspace_id]["document_count"] = max(
                0, _memory_workspaces[workspace_id].get("document_count", 0) + delta
            )


workspace_repo = WorkspaceRepository()
