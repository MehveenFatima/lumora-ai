from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime, timezone
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory document storage fallback
_memory_documents: Dict[str, Dict[str, Any]] = {}


class DocumentRepository:
    async def create(
        self,
        workspace_id: str,
        title: str,
        filename: str,
        file_type: str,
        file_size: int,
        storage_path: Optional[str] = None,
        page_count: int = 1,
        status: str = "uploading",
    ) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc_data = {
            "id": doc_id,
            "workspace_id": workspace_id,
            "title": title,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "storage_path": storage_path,
            "page_count": page_count,
            "status": status,
            "chunk_count": 0,
            "summary": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        }

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO documents 
                        (id, workspace_id, title, filename, file_type, file_size, storage_path, page_count, status, chunk_count, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        """,
                        uuid.UUID(doc_id),
                        workspace_id,
                        title,
                        filename,
                        file_type,
                        file_size,
                        storage_path,
                        page_count,
                        status,
                        0,
                        now,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error inserting document into DB: {e}")

        _memory_documents[doc_id] = doc_data
        return doc_data

    async def get_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM documents WHERE id = $1", uuid.UUID(document_id)
                    )
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error(f"Error fetching document {document_id}: {e}")
        return _memory_documents.get(document_id)

    async def list_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM documents WHERE workspace_id = $1 ORDER BY created_at DESC",
                        workspace_id,
                    )
                    if rows:
                        return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error listing documents for workspace {workspace_id}: {e}")

        return [
            doc
            for doc in _memory_documents.values()
            if doc["workspace_id"] == workspace_id
        ]

    async def update_status(
        self,
        document_id: str,
        status: str,
        page_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        summary: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE documents 
                        SET status = $2, 
                            page_count = COALESCE($3, page_count), 
                            chunk_count = COALESCE($4, chunk_count),
                            summary = COALESCE($5, summary),
                            error_message = $6,
                            updated_at = $7
                        WHERE id = $1
                        """,
                        uuid.UUID(document_id),
                        status,
                        page_count,
                        chunk_count,
                        summary,
                        error_message,
                        now,
                    )
            except Exception as e:
                logger.error(f"Error updating document status {document_id}: {e}")

        if document_id in _memory_documents:
            doc = _memory_documents[document_id]
            doc["status"] = status
            if page_count is not None:
                doc["page_count"] = page_count
            if chunk_count is not None:
                doc["chunk_count"] = chunk_count
            if summary is not None:
                doc["summary"] = summary
            doc["error_message"] = error_message
            doc["updated_at"] = now
            return doc
        return None

    async def delete(self, document_id: str) -> bool:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM documents WHERE id = $1", uuid.UUID(document_id)
                    )
            except Exception as e:
                logger.error(f"Error deleting document {document_id}: {e}")

        if document_id in _memory_documents:
            del _memory_documents[document_id]
            return True
        return False


document_repo = DocumentRepository()
