from typing import List, Dict, Any, Optional
import uuid
import json
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
                            uuid.UUID(c["id"]) if isinstance(c["id"], str) and len(c["id"]) == 36 else uuid.uuid4(),
                            c["workspace_id"],
                            uuid.UUID(c["document_id"]) if isinstance(c["document_id"], str) and len(c["document_id"]) == 36 else uuid.uuid4(),
                            c["chunk_index"],
                            c.get("page_number", 1),
                            c.get("heading"),
                            c["text"],
                            c.get("token_count"),
                            str(c["embedding"]),
                            json.dumps(c.get("metadata", {})) if isinstance(c.get("metadata"), (dict, list)) else (c.get("metadata") or "{}"),
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

    async def get_chunks_by_document(
        self,
        workspace_id: str,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all chunks for a specific document.
        STRICTLY SCOPED to the specified workspace_id and document_id.
        """
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
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
                            d.title as document_title
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND c.document_id = $2
                        ORDER BY c.page_number ASC, c.chunk_index ASC
                        """,
                        workspace_id,
                        uuid.UUID(document_id) if len(document_id) == 36 else document_id,
                    )
                    return [
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
                            "similarity_score": 1.0,
                        }
                        for r in rows
                    ]
            except Exception as e:
                logger.error(f"Error fetching chunks by document from DB: {e}")

        # In-memory store fallback
        matching = [
            c for c in _memory_chunks.values()
            if c["workspace_id"] == workspace_id and str(c["document_id"]) == str(document_id)
        ]
        matching.sort(key=lambda x: (x.get("page_number", 1), x.get("chunk_index", 0)))
        return [
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
                "similarity_score": 1.0,
            }
            for item in matching
        ]

    async def get_sampled_chunks_by_document(
        self,
        workspace_id: str,
        document_id: str,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves representative chunks sampled across all pages/sections of a specific document.
        STRICTLY SCOPED to the specified workspace_id and document_id.
        """
        results: List[Dict[str, Any]] = []
        pool = await get_db_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
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
                            d.title as document_title
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND c.document_id = $2
                        ORDER BY c.page_number ASC, c.chunk_index ASC
                        """,
                        workspace_id,
                        uuid.UUID(document_id) if len(document_id) == 36 else document_id,
                    )
                    all_chunks = [
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
                            "similarity_score": 0.95 - (0.02 * idx),
                        }
                        for idx, r in enumerate(rows)
                    ]
                    if len(all_chunks) <= limit:
                        return all_chunks
                    # Sample evenly across pages
                    step = len(all_chunks) / float(limit)
                    sampled = [all_chunks[int(i * step)] for i in range(limit)]
                    return sampled
            except Exception as e:
                logger.error(f"Error fetching sampled chunks from DB: {e}")

        # In-memory sampling fallback
        matching = [
            c for c in _memory_chunks.values()
            if c["workspace_id"] == workspace_id and str(c["document_id"]) == str(document_id)
        ]
        matching.sort(key=lambda x: (x.get("page_number", 1), x.get("chunk_index", 0)))

        if not matching:
            return []

        if len(matching) <= limit:
            return [
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
                    "similarity_score": 0.96 - (0.02 * idx),
                }
                for idx, item in enumerate(matching)
            ]

        step = len(matching) / float(limit)
        sampled = [matching[int(i * step)] for i in range(limit)]
        return [
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
                "similarity_score": 0.96 - (0.02 * idx),
            }
            for idx, item in enumerate(sampled)
        ]

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
                            c.metadata,
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
                        meta = r["metadata"]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except Exception:
                                meta = {}
                        elif not isinstance(meta, dict):
                            meta = {}
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
                                "metadata": meta,
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
                    "metadata": item.get("metadata", {}),
                    "similarity_score": item["similarity_score"],
                }
            )

        return results

    async def search_lexical_chunks(
        self,
        workspace_id: str,
        query_tokens: List[str],
        top_k: int = 15,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs workspace-wide lexical search matching tokens against text and heading across all chunks.
        """
        results: List[Dict[str, Any]] = []
        if not query_tokens:
            return results

        clean_tokens = [t.lower() for t in query_tokens if len(t) >= 2]
        if not clean_tokens:
            return results

        pool = await get_db_pool()
        if pool:
            try:
                doc_uuid = uuid.UUID(str(document_id)) if document_id and len(str(document_id)) == 36 else None
                async with pool.acquire() as conn:
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
                            c.metadata,
                            d.filename as document_name,
                            d.title as document_title
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND ($2::uuid IS NULL OR c.document_id = $2::uuid)
                        """,
                        workspace_id,
                        doc_uuid,
                    )
                    scored_rows = []
                    for r in rows:
                        text_lower = (r["text"] or "").lower()
                        heading_lower = (r["heading"] or "").lower()
                        doc_name_lower = (r["document_name"] or "").lower()
                        meta = r["metadata"]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except Exception:
                                meta = {}
                        elif not isinstance(meta, dict):
                            meta = {}

                        matches = 0
                        heading_matches = 0
                        for tok in clean_tokens:
                            if tok in heading_lower:
                                heading_matches += 1
                                matches += 2
                            elif tok in text_lower:
                                matches += 1
                            elif tok in doc_name_lower:
                                matches += 1

                        if matches > 0:
                            score = min(1.0, (matches / (len(clean_tokens) * 1.5)) + (0.1 if heading_matches else 0.0))
                            scored_rows.append((r, score, meta))

                    scored_rows.sort(key=lambda x: x[1], reverse=True)
                    for r, score, meta in scored_rows[:top_k]:
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
                                "metadata": meta,
                                "lexical_score": score,
                            }
                        )
                    return results
            except Exception as e:
                logger.error(f"Error executing lexical search in DB: {e}")

        # In-memory fallback
        matching = []
        for c in _memory_chunks.values():
            if c["workspace_id"] != workspace_id:
                continue
            if document_id and str(c.get("document_id")) != str(document_id):
                continue
            text_lower = (c.get("text") or "").lower()
            heading_lower = (c.get("heading") or "").lower()
            matches = sum(1 for tok in clean_tokens if tok in text_lower or tok in heading_lower)
            if matches > 0:
                score = min(1.0, matches / len(clean_tokens))
                matching.append(({**c, "lexical_score": score}, score))
        matching.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in matching[:top_k]]

    async def get_chunks_by_page(
        self,
        workspace_id: str,
        document_id: str,
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all chunks for a specific page of a document.
        STRICTLY SCOPED to workspace_id and document_id.
        """
        results: List[Dict[str, Any]] = []
        pool = await get_db_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
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
                            d.title as document_title
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND c.document_id = $2
                          AND c.page_number = $3
                        ORDER BY c.chunk_index ASC
                        """,
                        workspace_id,
                        uuid.UUID(document_id) if len(document_id) == 36 else document_id,
                        page_number,
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
                                "page_number": r["page_number"] or page_number,
                                "heading": r["heading"],
                                "text": r["text"],
                                "similarity_score": 1.0,
                            }
                        )
                    return results
            except Exception as e:
                logger.error(f"Error fetching page chunks from DB: {e}")

        # In-memory fallback
        matching = [
            c for c in _memory_chunks.values()
            if c["workspace_id"] == workspace_id
            and str(c["document_id"]) == str(document_id)
            and c.get("page_number", 1) == page_number
        ]
        matching.sort(key=lambda x: x.get("chunk_index", 0))
        return [
            {
                "id": item["id"],
                "workspace_id": item["workspace_id"],
                "document_id": item["document_id"],
                "document_name": item.get("document_name", "Workspace Document"),
                "document_title": item.get("document_title", "Document"),
                "chunk_index": item["chunk_index"],
                "page_number": item.get("page_number", page_number),
                "heading": item.get("heading"),
                "text": item["text"],
                "similarity_score": 1.0,
            }
            for item in matching
        ]

    async def get_chunks_by_page_range(
        self,
        workspace_id: str,
        document_id: str,
        start_page: int,
        end_page: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all chunks for a page range of a document.
        STRICTLY SCOPED to workspace_id and document_id.
        """
        results: List[Dict[str, Any]] = []
        pool = await get_db_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
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
                            d.title as document_title
                        FROM document_chunks c
                        JOIN documents d ON d.id = c.document_id
                        WHERE c.workspace_id = $1
                          AND c.document_id = $2
                          AND c.page_number BETWEEN $3 AND $4
                        ORDER BY c.page_number ASC, c.chunk_index ASC
                        """,
                        workspace_id,
                        uuid.UUID(document_id) if len(document_id) == 36 else document_id,
                        start_page,
                        end_page,
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
                                "page_number": r["page_number"] or start_page,
                                "heading": r["heading"],
                                "text": r["text"],
                                "similarity_score": 1.0,
                            }
                        )
                    return results
            except Exception as e:
                logger.error(f"Error fetching page range chunks from DB: {e}")

        # In-memory fallback
        matching = [
            c for c in _memory_chunks.values()
            if c["workspace_id"] == workspace_id
            and str(c["document_id"]) == str(document_id)
            and start_page <= c.get("page_number", 1) <= end_page
        ]
        matching.sort(key=lambda x: (x.get("page_number", 1), x.get("chunk_index", 0)))
        return [
            {
                "id": item["id"],
                "workspace_id": item["workspace_id"],
                "document_id": item["document_id"],
                "document_name": item.get("document_name", "Workspace Document"),
                "document_title": item.get("document_title", "Document"),
                "chunk_index": item["chunk_index"],
                "page_number": item.get("page_number", start_page),
                "heading": item.get("heading"),
                "text": item["text"],
                "similarity_score": 1.0,
            }
            for item in matching
        ]

    async def delete_by_document(self, document_id: str) -> None:
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM document_chunks WHERE document_id = $1",
                        uuid.UUID(str(document_id)),
                    )
            except Exception as e:
                logger.error(f"Error deleting chunks for doc {document_id}: {e}")

        to_delete = [
            cid
            for cid, c in _memory_chunks.items()
            if str(c["document_id"]) == str(document_id)
        ]
        for cid in to_delete:
            del _memory_chunks[cid]


chunk_repo = ChunkRepository()
