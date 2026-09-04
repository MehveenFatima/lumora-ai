from typing import List, Dict, Any, Tuple, Optional
import time
import re
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.services.embeddings import embedding_service
from backend.app.services.query_understanding import (
    query_understanding_service,
    ResolvedQuery,
)
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class RetrievedChunk:
    def __init__(
        self,
        id: str,
        document_id: str,
        document_name: str,
        page_number: int,
        heading: str,
        text: str,
        similarity_score: float,
    ):
        self.id = id
        self.document_id = document_id
        self.document_name = document_name
        self.page_number = page_number
        self.heading = heading
        self.text = text
        self.similarity_score = round(similarity_score, 4)

    def to_citation_dict(self) -> Dict[str, Any]:
        excerpt = self.text.replace("\n", " ").strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "..."
        return {
            "id": f"cit_{self.id[:8]}",
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page_or_slide": self.page_number,
            "excerpt": excerpt,
            "relevance_score": self.similarity_score,
        }


class RetrievalService:
    def __init__(
        self,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
        max_context_tokens: int = settings.max_context_tokens,
    ):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.max_context_tokens = max_context_tokens

    async def retrieve_relevant_chunks(
        self,
        workspace_id: str,
        query: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
        current_document_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[List[RetrievedChunk], bool, ResolvedQuery]:
        """
        Executes deterministic, strategy-driven retrieval based on resolved query intent.
        """
        start_time = time.time()
        resolved = await query_understanding_service.resolve_user_reference(
            workspace_id=workspace_id,
            user_message=query,
            recent_history=recent_history,
            current_document_id=current_document_id,
        )

        raw_chunks: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Strategy A: WORKSPACE_METADATA & AMBIGUOUS_DOCUMENT (No vector retrieval)
        # -------------------------------------------------------------
        if resolved.intent in ["WORKSPACE_METADATA", "AMBIGUOUS_DOCUMENT"]:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(
                f"[RAG Observability] request_id='{request_id or 'none'}' | "
                f"workspace_id='{workspace_id}' | conversation_id='{conversation_id or 'none'}' | "
                f"intent='{resolved.intent}' | resolved_doc='{resolved.target_document_id or 'none'}' | "
                f"resolved_page='{resolved.page_number or 'none'}' | "
                f"resolved_range='{f'{resolved.page_start}-{resolved.page_end}' if resolved.page_start else 'none'}' | "
                f"resolved_ref='{resolved.resolved_reference or 'none'}' | "
                f"semantic_query='{resolved.semantic_query[:60]}' | chunks_retrieved=0 | pages=[] | "
                f"scores=[] | model='{settings.gemini_model}' | latency_ms={latency_ms} | status='SUCCESS'"
            )
            return [], (resolved.intent == "WORKSPACE_METADATA"), resolved

        # -------------------------------------------------------------
        # Strategy B: PAGE_REFERENCE (Deterministic single page lookup)
        # -------------------------------------------------------------
        if resolved.intent == "PAGE_REFERENCE":
            if not resolved.clarification_message and resolved.target_document_id and resolved.page_number:
                raw_chunks = await chunk_repo.get_chunks_by_page(
                    workspace_id=workspace_id,
                    document_id=resolved.target_document_id,
                    page_number=resolved.page_number,
                )
                if not raw_chunks:
                    resolved.clarification_message = (
                        f"Page {resolved.page_number} exists in **{resolved.target_document_name}**, "
                        "but no extractable text was found on that page."
                    )

        # -------------------------------------------------------------
        # Strategy C: PAGE_RANGE_REFERENCE (Deterministic page range lookup)
        # -------------------------------------------------------------
        elif resolved.intent == "PAGE_RANGE_REFERENCE":
            if not resolved.clarification_message and resolved.target_document_id and resolved.page_start and resolved.page_end:
                raw_chunks = await chunk_repo.get_chunks_by_page_range(
                    workspace_id=workspace_id,
                    document_id=resolved.target_document_id,
                    start_page=resolved.page_start,
                    end_page=resolved.page_end,
                )
                if not raw_chunks:
                    resolved.clarification_message = (
                        f"Pages {resolved.page_start} to {resolved.page_end} exist in **{resolved.target_document_name}**, "
                        "but no extractable text was found on those pages."
                    )

        # -------------------------------------------------------------
        # Strategy D: DOCUMENT_SUMMARY / DOCUMENT_TOPIC_QUERY (Representative sampling)
        # -------------------------------------------------------------
        elif resolved.intent in ["DOCUMENT_SUMMARY", "DOCUMENT_TOPIC_QUERY"] and resolved.target_document_id:
            raw_chunks = await chunk_repo.get_sampled_chunks_by_document(
                workspace_id=workspace_id,
                document_id=resolved.target_document_id,
                limit=8,
            )

        # -------------------------------------------------------------
        # Strategy E: CONTEXTUAL_FOLLOWUP (Hybrid keyword + semantic retrieval)
        # -------------------------------------------------------------
        elif resolved.intent == "CONTEXTUAL_FOLLOWUP":
            if resolved.resolved_concept and resolved.target_document_id:
                doc_chunks = await chunk_repo.get_sampled_chunks_by_document(
                    workspace_id=workspace_id,
                    document_id=resolved.target_document_id,
                    limit=15,
                )
                concept_words = [
                    w.lower()
                    for w in re.split(r"[\s\:\-\_\,\?\.\!]+", resolved.resolved_concept)
                    if len(w) >= 3 and w.lower() not in ["and", "the", "for", "with", "from"]
                ]
                matching_chunks = []
                for dc in doc_chunks:
                    chunk_text_lower = dc["text"].lower()
                    chunk_heading_lower = (dc.get("heading") or "").lower()
                    matches = sum(1 for cw in concept_words if cw in chunk_text_lower or cw in chunk_heading_lower)
                    if matches > 0:
                        matching_chunks.append({**dc, "similarity_score": min(0.98, 0.88 + (0.03 * matches))})

                if matching_chunks:
                    raw_chunks = sorted(matching_chunks, key=lambda x: x["similarity_score"], reverse=True)[:5]

            # If hybrid matching didn't match, run pgvector search
            if not raw_chunks:
                query_embedding = await embedding_service.get_query_embedding(resolved.semantic_query)
                raw_chunks = await chunk_repo.search_similar_chunks(
                    workspace_id=workspace_id,
                    query_embedding=query_embedding,
                    top_k=max(self.top_k, 6),
                    similarity_threshold=0.35,
                )
                if resolved.target_document_id and raw_chunks:
                    filtered = [c for c in raw_chunks if str(c.get("document_id")) == resolved.target_document_id]
                    if filtered:
                        raw_chunks = filtered

        # -------------------------------------------------------------
        # Strategy F: SPECIFIC_CONCEPT (Hybrid keyword + pgvector retrieval)
        # -------------------------------------------------------------
        if not raw_chunks and not resolved.clarification_message and resolved.intent in ["SPECIFIC_CONCEPT", "CONTEXTUAL_FOLLOWUP"]:
            # 1. High-precision keyword / concept matching across workspace chunks
            all_ws_docs = await document_repo.list_by_workspace(workspace_id)
            target_docs = (
                [d for d in all_ws_docs if str(d["id"]) == resolved.target_document_id]
                if resolved.target_document_id
                else all_ws_docs
            )

            query_words = [
                w.lower()
                for w in re.split(r"[\s\:\-\_\,\?\.\!\;]+", resolved.semantic_query)
                if len(w) >= 3
                and w.lower()
                not in [
                    "how",
                    "what",
                    "where",
                    "when",
                    "why",
                    "from",
                    "with",
                    "this",
                    "that",
                    "the",
                    "and",
                    "for",
                    "explain",
                    "does",
                    "say",
                    "are",
                    "is",
                    "between",
                ]
            ]

            matching_chunks = []
            for doc in target_docs:
                doc_chunks = await chunk_repo.get_sampled_chunks_by_document(
                    workspace_id=workspace_id,
                    document_id=str(doc["id"]),
                    limit=25,
                )
                for dc in doc_chunks:
                    chunk_text_lower = dc["text"].lower()
                    chunk_heading_lower = (dc.get("heading") or "").lower()
                    matches = sum(
                        1
                        for qw in query_words
                        if qw in chunk_text_lower or qw in chunk_heading_lower
                    )
                    if (
                        matches >= 2
                        or (len(query_words) == 1 and matches >= 1)
                        or (
                            any(
                                qw in ["bfs", "dfs", "bst", "heap", "quicksort", "mergesort"]
                                for qw in query_words
                            )
                            and matches >= 1
                        )
                    ):
                        matching_chunks.append(
                            {
                                **dc,
                                "similarity_score": min(0.99, 0.86 + (0.04 * matches)),
                            }
                        )

            if matching_chunks:
                raw_chunks = sorted(
                    matching_chunks, key=lambda x: x["similarity_score"], reverse=True
                )[:5]

            # 2. Vector search across workspace
            if not raw_chunks:
                query_embedding = await embedding_service.get_query_embedding(
                    resolved.semantic_query
                )
                raw_chunks = await chunk_repo.search_similar_chunks(
                    workspace_id=workspace_id,
                    query_embedding=query_embedding,
                    top_k=self.top_k,
                    similarity_threshold=self.similarity_threshold,
                )
                if resolved.target_document_id and raw_chunks:
                    filtered = [
                        c
                        for c in raw_chunks
                        if str(c.get("document_id")) == resolved.target_document_id
                    ]
                    if filtered:
                        raw_chunks = filtered

        # Deduplicate and construct RetrievedChunk objects
        retrieved: List[RetrievedChunk] = []
        seen_texts = set()
        total_words = 0

        for c in raw_chunks:
            normalized_text = " ".join(c["text"].split()[:30])
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)

            chunk_words = len(c["text"].split())
            if total_words + chunk_words > self.max_context_tokens:
                break

            total_words += chunk_words
            retrieved.append(
                RetrievedChunk(
                    id=str(c["id"]),
                    document_id=str(c["document_id"]),
                    document_name=c.get("document_name", resolved.target_document_name or "Workspace Document"),
                    page_number=c.get("page_number", 1),
                    heading=c.get("heading") or "",
                    text=c["text"],
                    similarity_score=c.get("similarity_score", 0.95),
                )
            )

        retrieved_pages = sorted(list(set(c.page_number for c in retrieved)))
        retrieved_scores = [c.similarity_score for c in retrieved]
        is_grounded = len(retrieved) > 0 and not bool(resolved.clarification_message)
        latency_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            f"[RAG Observability] request_id='{request_id or 'none'}' | "
            f"workspace_id='{workspace_id}' | conversation_id='{conversation_id or 'none'}' | "
            f"intent='{resolved.intent}' | resolved_doc='{resolved.target_document_id or 'none'}' | "
            f"resolved_page='{resolved.page_number or 'none'}' | "
            f"resolved_range='{f'{resolved.page_start}-{resolved.page_end}' if resolved.page_start else 'none'}' | "
            f"resolved_ref='{resolved.resolved_reference or 'none'}' | "
            f"semantic_query='{resolved.semantic_query[:60]}' | chunks_retrieved={len(retrieved)} | "
            f"pages={retrieved_pages} | scores={retrieved_scores} | model='{settings.gemini_model}' | "
            f"latency_ms={latency_ms} | status='{'GROUNDED' if is_grounded else 'UNGROUNDED'}'"
        )

        return retrieved, is_grounded, resolved


retrieval_service = RetrievalService()
