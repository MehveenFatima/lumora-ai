from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone
import numpy as np
from backend.app.db.connection import get_db_pool
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory chunks storage fallback
_memory_chunks: Dict[str, Dict[str, Any]] = {}


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class ChunkRepository:
    async def insert_chunks(self, chunks_data: List[Dict[str, Any]]) -> None:
        if not chunks_data:
            return

        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    # Prepare batch records
                    records = [
                        (
                            uuid.UUID(c["id"]),
                            c["workspace_id"],
                            uuid.UUID(c["document_id"]),
                            c["chunk_index"],
                            c.get("page_number", 1),
                            c.get("heading"),
                            c["text"],
                            c.get("token_count"),
                            str(c["embedding"]),  # pgvector string representation: '[0.1, 0.2, ...]'
                            c.get("metadata", {}),
                            datetime.now(timezone.utc),
                        )
                        for c in chunks_data
                    ]
                    await conn.executemany(
                        """
                        INSERT INTO document_chunks 
                        (id, workspace_id, document_id, chunk_index, page_number, heading, text, token_count, embedding, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10, $11)
                        """,
                        records,
                    )
            except Exception as e:
                logger.error(f"Error inserting chunks into DB: {e}")

        # In-memory store
        for c in chunks_data:
            _memory_chunks[c["id"]] = c

    async def search_similar_chunks(
        self,
        workspace_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        similarity_threshold: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k chunks matching the query embedding.
        STRICTLY SCOPED to the specified workspace_id.
        """
        results: List[Dict[str, Any]] = []
        pool = await get_db_pool()

        if pool:
            try:
                embedding_str = f"[{','.join(map(str, query_embedding))}]"
                async with pool.acquire() as conn:
                    # Cosine distance: 1 - (embedding <=> query) = similarity
                    rows = await conn.fetch(
                        """
                        SELECT 
                            c.id,
                            c.workspace_id,
                            c.document_id,
                            c.chunk_index,
                            c.page_number,
                            c.heading,
                            c.text,
                            d.filename as document_name,
                            d.title as document_title,
                            1 - (c.embedding <=> $2::vector) AS similarity_score
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND 1 - (c.embedding <=> $2::vector) >= $3
                        ORDER BY similarity_score DESC
                        LIMIT $4
                        """,
                        workspace_id,
                        embedding_str,
                        similarity_threshold,
                        top_k,
                    )
                    for r in rows:
                        results.append(
                            {
                                "id": str(r["id"]),
                                "workspace_id": r["workspace_id"],
                                "document_id": str(r["document_id"]),
                                "document_name": r["document_name"],
                                "document_title": r["document_title"],
                                "chunk_index": r["chunk_index"],
                                "page_number": r["page_number"] or 1,
                                "heading": r["heading"],
                                "text": r["text"],
                                "similarity_score": float(r["similarity_score"]),
                            }
                        )
                return results
            except Exception as e:
                logger.error(f"Error executing vector similarity search in DB: {e}")

        # In-memory scoped vector search fallback
        scoped_chunks = [
            c for c in _memory_chunks.values() if c["workspace_id"] == workspace_id
        ]
        scored_chunks = []

        for chunk in scoped_chunks:
            if "embedding" in chunk and chunk["embedding"]:
                score = cosine_similarity(query_embedding, chunk["embedding"])
                if score >= similarity_threshold:
                    scored_chunks.append({**chunk, "similarity_score": score})

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_results = scored_chunks[:top_k]

        for item in top_results:
            results.append(
                {
                    "id": item["id"],
                    "workspace_id": item["workspace_id"],
                    "document_id": item["document_id"],
                    "document_name": item.get("document_name", "Workspace Document"),
                    "document_title": item.get("document_title", "Document"),
                    "chunk_index": item["chunk_index"],
                    "page_number": item.get("page_number", 1),
                    "heading": item.get("heading"),
                    "text": item["text"],
                    "similarity_score": item["similarity_score"],
                }
            )

        return results

    async def delete_by_document(self, document_id: str) -> None:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM document_chunks WHERE document_id = $1",
                        uuid.UUID(document_id),
                    )
            except Exception as e:
                logger.error(f"Error deleting chunks for doc {document_id}: {e}")

        to_delete = [
            cid
            for cid, c in _memory_chunks.items()
            if c["document_id"] == document_id
        ]
        for cid in to_delete:
            del _memory_chunks[cid]


chunk_repo = ChunkRepository()
