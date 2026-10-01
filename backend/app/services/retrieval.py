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

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to", "for",
    "with", "by", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "from", "up", "down", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "can", "could", "should", "would", "may", "might", "must", "shall",
    "what", "how", "why", "when", "where", "who", "which", "explain", "describe",
    "tell", "give", "me", "you", "this", "that", "these", "those", "it", "its",
    "we", "they", "them", "their", "of", "as", "such",
}


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
        workspace_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.workspace_id = workspace_id
        self.document_id = document_id
        self.document_name = document_name
        self.page_number = page_number
        self.heading = heading or ""
        self.text = text
        self.similarity_score = round(similarity_score, 4)
        self.metadata = metadata or {}

    @property
    def has_table(self) -> bool:
        return bool(self.metadata.get("has_table") or "|" in self.text and "---" in self.text)

    @property
    def has_diagram(self) -> bool:
        return bool(self.metadata.get("has_diagram"))

    @property
    def figure_captions(self) -> List[str]:
        return self.metadata.get("figure_captions", [])

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
        similarity_threshold: float = 0.50,  # Validated empirical threshold
        max_context_tokens: int = settings.max_context_tokens,
    ):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.max_context_tokens = max_context_tokens

    async def _vector_search(
        self, workspace_id: str, text: str, top_k: int, similarity_threshold: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Vector search that compares the query only with chunks embedded by the same model.
        A workspace can hold chunks from more than one model (for example offline-seeded data
        and documents uploaded with a Gemini key), so each group is searched with a query
        embedded in its own vector space.
        """
        results: List[Dict[str, Any]] = []
        for model in await chunk_repo.list_embedding_models(workspace_id):
            query_emb = await embedding_service.embed_query_for(text, model or None)
            if query_emb is None:
                continue
            results.extend(
                await chunk_repo.search_similar_chunks(
                    workspace_id,
                    query_emb,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                    embedding_model=model,
                )
            )
        return results

    def _extract_query_tokens(self, query_text: str) -> List[str]:
        words = re.split(r"[\s\:\-\_\,\?\.\!\;\'\"\(\)\[\]]+", query_text.lower())
        tokens = [w for w in words if len(w) >= 2 and w not in STOP_WORDS]
        return tokens

    def _deterministic_rerank(
        self,
        candidates: List[Dict[str, Any]],
        query_tokens: List[str],
        resolved: ResolvedQuery,
        target_k: int,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic final reranker based on:
        - vector similarity (0.0 to 1.0)
        - lexical relevance (0.0 to 1.0)
        - heading / title exact match bonus (+0.10)
        - section match bonus (+0.05)
        - page/slide match bonus (+0.25)
        - table / diagram intent bonus (+0.20)
        - diversity penalty across same-page chunks
        """
        # Merge candidates by chunk ID to preserve both vector and lexical scores
        chunk_map: Dict[str, Dict[str, Any]] = {}
        for c in candidates:
            cid = str(c["id"])
            if cid not in chunk_map:
                chunk_map[cid] = dict(c)
            else:
                existing = chunk_map[cid]
                if "similarity_score" in c and (c.get("similarity_score") or 0.0) > (existing.get("similarity_score") or 0.0):
                    existing["similarity_score"] = c["similarity_score"]
                if "lexical_score" in c and (c.get("lexical_score") or 0.0) > (existing.get("lexical_score") or 0.0):
                    existing["lexical_score"] = c["lexical_score"]

        merged_candidates = list(chunk_map.values())
        scored_candidates = []
        page_counts: Dict[int, int] = {}

        for c in merged_candidates:
            vec_score = float(c.get("similarity_score") or 0.0)
            lex_score = float(c.get("lexical_score") or 0.0)

            text_lower = (c.get("text") or "").lower()
            heading_lower = (c.get("heading") or "").lower()
            doc_name_lower = (c.get("document_name") or "").lower()
            meta = c.get("metadata") or {}

            # Heading & Document Name Match Bonus
            heading_bonus = 0.0
            if query_tokens:
                head_matches = sum(1 for tok in query_tokens if tok in heading_lower or tok in doc_name_lower)
                if head_matches >= 1:
                    heading_bonus = min(0.12, 0.05 * head_matches)

            # Section breadcrumb bonus
            section_bonus = 0.0
            breadcrumbs = meta.get("section_breadcrumbs", [])
            if breadcrumbs and query_tokens:
                bc_str = " ".join(breadcrumbs).lower()
                if any(tok in bc_str for tok in query_tokens):
                    section_bonus = 0.05

            # Page / Slide Match Bonus
            page_bonus = 0.0
            page_num = c.get("page_number", 1)
            if resolved.page_number and page_num == resolved.page_number:
                page_bonus = 0.25
            elif resolved.page_start and resolved.page_end and (resolved.page_start <= page_num <= resolved.page_end):
                page_bonus = 0.20

            # Table & Diagram Intent Bonus
            visual_bonus = 0.0
            if resolved.is_table_query and (meta.get("has_table") or "|" in c.get("text", "")):
                visual_bonus = 0.20
            elif resolved.is_visual_query and (meta.get("has_diagram") or meta.get("figure_captions")):
                visual_bonus = 0.20

            # Base relevance fusion (does not penalize pure vector matches for paraphrased questions)
            if vec_score > 0 and lex_score > 0:
                base_score = max(vec_score, 0.65 * vec_score + 0.35 * lex_score)
            elif vec_score > 0:
                base_score = vec_score
            else:
                base_score = lex_score

            base_score += heading_bonus + section_bonus + page_bonus + visual_bonus

            # Diversity decay: if we already picked chunks from this page, apply small decay
            seen_count = page_counts.get(page_num, 0)
            decay = max(0.0, 0.04 * seen_count)
            final_score = min(0.99, max(0.0, base_score - decay))
            page_counts[page_num] = seen_count + 1

            scored_candidates.append({**c, "final_score": final_score})

        # Sort descending by final deterministic score
        scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # Deduplicate identical or near-identical text
        unique_results = []
        seen_snippets = set()

        for sc in scored_candidates:
            snip = " ".join((sc.get("text") or "").split()[:20])
            if snip in seen_snippets:
                continue
            seen_snippets.add(snip)
            unique_results.append(sc)
            if len(unique_results) >= target_k:
                break

        return unique_results

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
        Executes deterministic, strategy-driven hybrid retrieval and reranking.
        Grounding is strictly determined by post-retrieval evidence sufficiency.
        """
        start_time = time.time()
        resolved = await query_understanding_service.resolve_user_reference(
            workspace_id=workspace_id,
            user_message=query,
            recent_history=recent_history,
            current_document_id=current_document_id,
        )

        # Strategy A: WORKSPACE_METADATA or Clarification boundary
        if resolved.intent == "WORKSPACE_METADATA":
            return [], True, resolved
        if resolved.clarification_message or resolved.intent == "AMBIGUOUS_DOCUMENT":
            return [], False, resolved

        candidate_chunks: List[Dict[str, Any]] = []
        query_tokens = self._extract_query_tokens(resolved.semantic_query)

        # -------------------------------------------------------------
        # 1. Deterministic Page / Range Retrieval
        # -------------------------------------------------------------
        if resolved.intent == "PAGE_REFERENCE" and resolved.target_document_id and resolved.page_number:
            page_chunks = await chunk_repo.get_chunks_by_page(
                workspace_id=workspace_id,
                document_id=resolved.target_document_id,
                page_number=resolved.page_number,
            )
            for pc in page_chunks:
                candidate_chunks.append({**pc, "similarity_score": 1.0, "lexical_score": 1.0})

        elif resolved.intent == "PAGE_RANGE_REFERENCE" and resolved.target_document_id and resolved.page_start and resolved.page_end:
            range_chunks = await chunk_repo.get_chunks_by_page_range(
                workspace_id=workspace_id,
                document_id=resolved.target_document_id,
                start_page=resolved.page_start,
                end_page=resolved.page_end,
            )
            for rc in range_chunks:
                candidate_chunks.append({**rc, "similarity_score": 0.98, "lexical_score": 0.98})

        # -------------------------------------------------------------
        # 2. Document Summary / Topic Query
        # -------------------------------------------------------------
        elif resolved.intent in ["DOCUMENT_SUMMARY", "DOCUMENT_TOPIC_QUERY"] and resolved.target_document_id:
            summary_chunks = await chunk_repo.get_sampled_chunks_by_document(
                workspace_id=workspace_id,
                document_id=resolved.target_document_id,
                limit=max(self.top_k, 8),
            )
            for sc in summary_chunks:
                candidate_chunks.append({**sc, "similarity_score": 0.95, "lexical_score": 0.90})

        # -------------------------------------------------------------
        # 3. Compare / Contrast Retrieval (Dual-Concept Hybrid)
        # -------------------------------------------------------------
        elif resolved.intent == "COMPARE_CONTRAST" and resolved.resolved_concept_a and resolved.resolved_concept_b:
            vec_a = await self._vector_search(workspace_id, resolved.resolved_concept_a, top_k=4)
            vec_b = await self._vector_search(workspace_id, resolved.resolved_concept_b, top_k=4)

            tokens_a = self._extract_query_tokens(resolved.resolved_concept_a)
            tokens_b = self._extract_query_tokens(resolved.resolved_concept_b)

            lex_a = await chunk_repo.search_lexical_chunks(workspace_id, tokens_a, top_k=4, document_id=resolved.target_document_id)
            lex_b = await chunk_repo.search_lexical_chunks(workspace_id, tokens_b, top_k=4, document_id=resolved.target_document_id)

            candidate_chunks.extend(vec_a)
            candidate_chunks.extend(vec_b)
            candidate_chunks.extend(lex_a)
            candidate_chunks.extend(lex_b)

        # -------------------------------------------------------------
        # 4. Standard Hybrid Retrieval (Vector + Lexical)
        # -------------------------------------------------------------
        if not candidate_chunks:
            # A. Vector Retrieval
            vec_candidates = await self._vector_search(
                workspace_id, resolved.semantic_query, top_k=max(self.top_k * 2, 8)
            )
            candidate_chunks.extend(vec_candidates)

            # B. Lexical Retrieval across ALL workspace chunks
            if query_tokens:
                lex_candidates = await chunk_repo.search_lexical_chunks(
                    workspace_id=workspace_id,
                    query_tokens=query_tokens,
                    top_k=max(self.top_k * 2, 8),
                    document_id=resolved.target_document_id,
                )
                candidate_chunks.extend(lex_candidates)

        # Filter by target document if explicitly bound
        if resolved.target_document_id and candidate_chunks:
            doc_filtered = [c for c in candidate_chunks if str(c.get("document_id")) == resolved.target_document_id]
            if doc_filtered:
                candidate_chunks = doc_filtered

        # -------------------------------------------------------------
        # 5. Deterministic Final Reranking & Diversity
        # -------------------------------------------------------------
        reranked = self._deterministic_rerank(
            candidates=candidate_chunks,
            query_tokens=query_tokens,
            resolved=resolved,
            target_k=self.top_k,
        )

        # -------------------------------------------------------------
        # 6. Evidence Sufficiency / Grounding Check
        # -------------------------------------------------------------
        # Grounding decision is made here, after retrieval and score fusion
        top_score = max((r.get("final_score", r.get("similarity_score", 0.0)) for r in reranked), default=0.0)

        # For general queries, verify against empirical threshold.
        # If query has substantive tokens but 0 lexical matches anywhere in workspace chunks,
        # require slightly stronger semantic threshold (0.52) to prevent out-of-domain false positives.
        has_any_lexical_match = any((r.get("lexical_score") or 0.0) > 0 for r in reranked)
        effective_threshold = self.similarity_threshold
        if query_tokens and not has_any_lexical_match:
            effective_threshold = max(self.similarity_threshold, 0.52)

        # If highest candidate similarity score is below threshold, reject truthfully
        is_grounded = bool(reranked) and (
            top_score >= effective_threshold
            or resolved.intent in ["PAGE_REFERENCE", "PAGE_RANGE_REFERENCE", "DOCUMENT_SUMMARY"]
            or (resolved.intent == "CONTEXTUAL_FOLLOWUP" and top_score >= 0.35)
        )

        retrieved: List[RetrievedChunk] = []
        if is_grounded:
            total_words = 0
            for r in reranked:
                text = r["text"]
                chunk_words = len(text.split())
                if total_words + chunk_words > self.max_context_tokens:
                    break
                total_words += chunk_words

                retrieved.append(
                    RetrievedChunk(
                        id=str(r["id"]),
                        document_id=str(r["document_id"]),
                        document_name=r.get("document_name", resolved.target_document_name or "Workspace Document"),
                        page_number=r.get("page_number", 1),
                        heading=r.get("heading") or "",
                        text=text,
                        similarity_score=r.get("final_score", r.get("similarity_score", 0.9)),
                        workspace_id=str(r.get("workspace_id", workspace_id)),
                        metadata=r.get("metadata", {}),
                    )
                )

        latency_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"[RAG Observability] request_id='{request_id or 'none'}' | "
            f"workspace_id='{workspace_id}' | conversation_id='{conversation_id or 'none'}' | "
            f"intent='{resolved.intent}' | resolved_doc='{resolved.target_document_id or 'none'}' | "
            f"resolved_page='{resolved.page_number or 'none'}' | "
            f"semantic_query='{resolved.semantic_query[:60]}' | chunks_retrieved={len(retrieved)} | "
            f"top_score={round(top_score, 4)} | latency_ms={latency_ms} | status='{'GROUNDED' if is_grounded else 'UNGROUNDED'}'"
        )

        return retrieved, is_grounded, resolved


retrieval_service = RetrievalService()

