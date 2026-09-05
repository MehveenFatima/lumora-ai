from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Baseline in-memory storage fallback for local execution & testing
_memory_workspaces: Dict[str, Dict[str, Any]] = {
    "dsa": {
        "id": "dsa",
        "name": "Data Structures & Algorithms",
        "goal": "Placement Prep 2026",
        "level": "intermediate",
        "target_date": "2026-12-31",
        "daily_target_minutes": 45,
        "description": "Master fundamental and advanced algorithmic problem solving.",
        "overall_mastery": 74,
        "mastery_delta": 5,
        "status": "on_track",
        "icon_name": "FolderKanban",
        "document_count": 0,
    },
    "os": {
        "id": "os",
        "name": "Operating Systems",
        "goal": "Semester 5 Core Prep",
        "level": "intermediate",
        "target_date": "2026-12-31",
        "daily_target_minutes": 45,
        "description": "Concurrency, virtual memory management, and file systems.",
        "overall_mastery": 64,
        "mastery_delta": 3,
        "status": "on_track",
        "icon_name": "Cpu",
        "document_count": 0,
    },
    "ml": {
        "id": "ml",
        "name": "Machine Learning & AI",
        "goal": "Certification Track",
        "level": "advanced",
        "target_date": "2026-12-31",
        "daily_target_minutes": 45,
        "description": "Statistical modeling, deep learning architectures, and transformers.",
        "overall_mastery": 57,
        "mastery_delta": 7,
        "status": "active",
        "icon_name": "BrainCircuit",
        "document_count": 0,
    },
    "aws": {
        "id": "aws",
        "name": "AWS Solutions Architect",
        "goal": "SAA-C03 Certification",
        "level": "beginner",
        "target_date": "2026-12-31",
        "daily_target_minutes": 45,
        "description": "Cloud architecture, high availability, VPC, and IAM policies.",
        "overall_mastery": 48,
        "mastery_delta": 4,
        "status": "active",
        "icon_name": "Network",
        "document_count": 0,
    },
}


class WorkspaceRepository:
    async def create(
        self,
        workspace_id: str,
        name: str,
        goal: str,
        level: str = "intermediate",
        target_date: Optional[str] = None,
        daily_target_minutes: int = 45,
        description: str = "",
        icon_name: str = "FolderKanban",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        # Ensure a clean YYYY-MM-DD string for PostgreSQL DATE casting
        clean_target_date = "2026-12-31"
        if target_date:
            try:
                candidate = str(target_date).strip()[:10]
                datetime.strptime(candidate, "%Y-%m-%d")
                clean_target_date = candidate
            except Exception:
                clean_target_date = "2026-12-31"

        ws_data = {
            "id": workspace_id,
            "name": name,
            "goal": goal,
            "level": level,
            "target_date": clean_target_date,
            "daily_target_minutes": daily_target_minutes,
            "description": description,
            "overall_mastery": 0,
            "mastery_delta": 0,
            "status": "active",
            "icon_name": icon_name,
            "document_count": 0,
            "topics_count": 0,
            "flashcards_due_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO workspaces 
                        (id, name, goal, level, target_date, daily_target_minutes, description, overall_mastery, mastery_delta, status, icon_name, document_count, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5::date, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            goal = EXCLUDED.goal,
                            description = EXCLUDED.description,
                            updated_at = EXCLUDED.updated_at
                        """,
                        workspace_id,
                        name,
                        goal,
                        level,
                        ws_data["target_date"],
                        daily_target_minutes,
                        description,
                        0,
                        0,
                        "active",
                        icon_name,
                        0,
                        now,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error inserting workspace {workspace_id} into DB: {e}")

        _memory_workspaces[workspace_id] = ws_data
        return ws_data

    async def get_by_id(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM workspaces WHERE id = $1", workspace_id
                    )
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error(f"Error getting workspace {workspace_id}: {e}")
        ws = _memory_workspaces.get(workspace_id)
        if ws:
            from backend.app.repositories.documents import document_repo
            docs = await document_repo.list_by_workspace(workspace_id)
            return {**ws, "document_count": len(docs)}
        return None

    async def list_all(self) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("SELECT * FROM workspaces ORDER BY created_at DESC")
                    if rows:
                        db_workspaces = [dict(r) for r in rows]
                        existing_ids = {w["id"] for w in db_workspaces}
                        for k, v in _memory_workspaces.items():
                            if k not in existing_ids:
                                db_workspaces.append(v)
                        return db_workspaces
            except Exception as e:
                logger.error(f"Error listing workspaces: {e}")
        ws_list = list(_memory_workspaces.values())
        from backend.app.repositories.documents import document_repo
        result = []
        for ws in ws_list:
            docs = await document_repo.list_by_workspace(ws["id"])
            result.append({**ws, "document_count": len(docs)})
        return result

    async def delete(self, workspace_id: str) -> bool:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("DELETE FROM workspaces WHERE id = $1", workspace_id)
            except Exception as e:
                logger.error(f"Error deleting workspace {workspace_id}: {e}")

        if workspace_id in _memory_workspaces:
            del _memory_workspaces[workspace_id]
            return True
        return False

    async def increment_doc_count(self, workspace_id: str, delta: int = 1) -> None:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE workspaces SET document_count = GREATEST(0, document_count + $2) WHERE id = $1",
                        workspace_id,
                        delta,
                    )
            except Exception as e:
                logger.error(f"Error incrementing doc count for workspace {workspace_id}: {e}")

    async def update_mastery(
        self,
        workspace_id: str,
        overall_mastery: int,
        mastery_delta: int = 0,
    ) -> None:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE workspaces 
                        SET overall_mastery = $2, mastery_delta = $3, updated_at = NOW()
                        WHERE id = $1
                        """,
                        workspace_id,
                        overall_mastery,
                        mastery_delta,
                    )
            except Exception as e:
                logger.error(f"Error updating mastery for workspace {workspace_id}: {e}")

        if workspace_id in _memory_workspaces:
            _memory_workspaces[workspace_id]["overall_mastery"] = overall_mastery
            _memory_workspaces[workspace_id]["mastery_delta"] = mastery_delta


workspace_repo = WorkspaceRepository()
