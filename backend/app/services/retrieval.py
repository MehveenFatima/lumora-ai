from typing import List, Dict, Any, Tuple, Optional
import re
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.services.embeddings import embedding_service
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

    def extract_concepts_from_history(
        self, recent_history: Optional[List[Dict[str, Any]]]
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Extracts structured concepts and last referenced document from the most recent assistant messages.
        Returns (concepts_list, last_document_id, last_document_name).
        """
        if not recent_history:
            return [], None, None

        last_assistant_msg = ""
        last_doc_id = None
        last_doc_name = None

        for msg in reversed(recent_history):
            if msg.get("role") == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg.get("content", "")
                citations = msg.get("citations", [])
                if citations and isinstance(citations, list) and len(citations) > 0:
                    last_doc_id = str(citations[0].get("document_id"))
                    last_doc_name = citations[0].get("document_name")

        if not last_assistant_msg:
            return [], last_doc_id, last_doc_name

        concepts: List[str] = []

        # 1. Numbered items: "1. SSL Handshake Protocol: ..." or "1. **SSL Handshake Protocol**"
        numbered = re.findall(
            r"(?:^|\n)\s*(?:\d+[\.\)]|\([0-9]+\))\s*(?:\*\*)?([^\n\:\-\*]+?)(?:\*\*)?(?:\:|\s*\-|\s*—|\n|$)",
            last_assistant_msg,
        )
        for c in numbered:
            clean_c = c.strip(" *#-_`").strip()
            if len(clean_c) >= 3 and clean_c.lower() not in [
                "core concept",
                "principles",
                "application",
                "step",
                "note",
                "summary",
                "overview",
                "conclusion",
            ]:
                concepts.append(clean_c)

        # 2. Bold headers: "**SSL Handshake Protocol**"
        if not concepts:
            bold_items = re.findall(r"\*\*([^\*\n]+?)\*\*", last_assistant_msg)
            for b in bold_items:
                clean_b = b.strip()
                if (
                    len(clean_b) >= 3
                    and len(clean_b.split()) <= 7
                    and not clean_b.lower().startswith("from ")
                    and not clean_b.lower().startswith("source")
                    and not clean_b.lower().startswith("based on")
                ):
                    concepts.append(clean_b)

        # 3. Bullet points: "- SSL Handshake: ..." or "* SSL Handshake: ..."
        if not concepts:
            bullets = re.findall(
                r"(?:^|\n)\s*[\-\*•]\s*([^\n\:\-]+?)(?:\:|\s*\-|\n|$)",
                last_assistant_msg,
            )
            for b in bullets:
                clean_b = b.strip(" *#-_`").strip()
                if len(clean_b) >= 3:
                    concepts.append(clean_b)

        return concepts, last_doc_id, last_doc_name

    async def resolve_document_and_intent(
        self,
        workspace_id: str,
        query: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], str]:
        """
        Resolves query intent and matches any referenced document or concept reference.
        Returns:
            (intent, target_document_id, target_document_name, resolved_reference, cleaned_query)
        """
        q_lower = query.lower().strip()
        docs = await document_repo.list_by_workspace(workspace_id)

        target_doc_id = None
        target_doc_name = None
        resolved_reference = None

        # 1. Check for WORKSPACE_METADATA intent
        metadata_patterns = [
            r"what (sources|documents|files|topics|materials) (are|do i have|exist|are indexed|are uploaded|are in this workspace|in this workspace)",
            r"how many (sources|documents|files|topics|pages) (are|do i have|exist|indexed|uploaded)",
            r"(show|list|tell) (me )?(all )?(available )?(sources|documents|files|topics|indexed)",
            r"what is (currently )?(indexed|in this workspace|uploaded)",
            r"which documents (are ready|do i have|are available)",
            r"what topics are (currently )?indexed",
            r"what files have i uploaded",
        ]
        if any(re.search(pat, q_lower) for pat in metadata_patterns):
            return "WORKSPACE_METADATA", None, None, None, query

        # 2. Match Explicit Filename or Title in Query
        for d in docs:
            fn = d.get("filename", "").lower()
            title = d.get("title", "").lower()
            fn_no_ext = fn.rsplit(".", 1)[0] if "." in fn else fn

            if (
                fn in q_lower
                or fn_no_ext in q_lower
                or (len(fn_no_ext) >= 4 and fn_no_ext.split()[0] in q_lower)
                or (title and title in q_lower)
            ):
                target_doc_id = str(d.get("id"))
                target_doc_name = d.get("filename")
                break

        # 3. Anaphoric document matching if single document in workspace
        if not target_doc_id and len(docs) == 1:
            doc_anaphors = [
                "this pdf",
                "this document",
                "this source",
                "this file",
                "the document",
                "the pdf",
                "the file",
            ]
            if any(term in q_lower for term in doc_anaphors):
                target_doc_id = str(docs[0].get("id"))
                target_doc_name = docs[0].get("filename")

        # 4. Check for CONTEXTUAL_FOLLOWUP (references to prior conversational turns)
        history_concepts, last_doc_id, last_doc_name = self.extract_concepts_from_history(recent_history)
        if not target_doc_id and last_doc_id:
            # Inherit active document from recent conversation if it belongs to current workspace
            if any(str(d.get("id")) == last_doc_id for d in docs):
                target_doc_id = last_doc_id
                target_doc_name = last_doc_name

        followup_patterns = [
            r"\b(first|1st)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(second|2nd)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(third|3rd)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(fourth|4th)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\b(last)\s+(concept|point|topic|item|algorithm|section|protocol|part)\b",
            r"\bexplain\s+(the\s+)?(first|second|third|fourth|last)\b",
            r"\b(concrete\s+)?example\s+of\s+(that|this|it|the\s+first|the\s+second)\b",
            r"\b(explain|simplify|break\s+down)\s+(it|that|this)\b",
            r"\b(simpler|simple)\s+terms\b",
            r"\b(what\s+you\s+just\s+explained|we\s+just\s+discussed|you\s+just\s+mentioned)\b",
            r"\bexam\s+points\s+(from|about|on)\b",
            r"\bwhy\s+is\s+(that|this|it)\s+(important|used|needed)\b",
            r"\bhow\s+does\s+(that|this|it)\s+work\b",
        ]

        is_followup = bool(recent_history) and any(re.search(pat, q_lower) for pat in followup_patterns)

        if is_followup and history_concepts:
            # Ordinal resolution
            if re.search(r"\b(first|1st)\b", q_lower) and len(history_concepts) >= 1:
                resolved_reference = history_concepts[0]
            elif re.search(r"\b(second|2nd)\b", q_lower) and len(history_concepts) >= 2:
                resolved_reference = history_concepts[1]
            elif re.search(r"\b(third|3rd)\b", q_lower) and len(history_concepts) >= 3:
                resolved_reference = history_concepts[2]
            elif re.search(r"\b(fourth|4th)\b", q_lower) and len(history_concepts) >= 4:
                resolved_reference = history_concepts[3]
            elif re.search(r"\b(last)\b", q_lower):
                resolved_reference = history_concepts[-1]
            else:
                # Default to primary concept in recent turn
                resolved_reference = history_concepts[0]

            cleaned_query = query
            if target_doc_name:
                cleaned_query = re.sub(re.escape(target_doc_name), "", cleaned_query, flags=re.IGNORECASE).strip()

            return "CONTEXTUAL_FOLLOWUP", target_doc_id, target_doc_name, resolved_reference, cleaned_query

        # 5. Clean query
        cleaned_query = query
        if target_doc_name:
            cleaned_query = re.sub(re.escape(target_doc_name), "", cleaned_query, flags=re.IGNORECASE).strip()

        # 6. Summary Intent
        summary_keywords = [
            "summar",
            "what are the concepts",
            "what concepts",
            "overview",
            "main topic",
            "main concepts",
            "all concepts",
            "syllabus",
            "tell me about this",
            "explain this pdf",
            "what is this document about",
            "key points",
            "important exam concepts",
            "table of contents",
        ]
        is_summary = any(k in q_lower for k in summary_keywords) or (
            target_doc_name and ("summarize it" in q_lower or "summarize" in q_lower)
        )

        intent = "DOCUMENT_SUMMARY" if is_summary else "SPECIFIC_CONCEPT"
        return intent, target_doc_id, target_doc_name, None, cleaned_query

    async def retrieve_relevant_chunks(
        self,
        workspace_id: str,
        query: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None,
    ) -> Tuple[List[RetrievedChunk], bool, str, Optional[str], Optional[str]]:
        """
        Retrieves relevant chunks within the specified workspace.
        Supports:
        - WORKSPACE_METADATA
        - CONTEXTUAL_FOLLOWUP (concept resolution from history)
        - DOCUMENT_SUMMARY (representative multi-page chunk sampling)
        - SPECIFIC_CONCEPT (pgvector semantic similarity)
        """
        intent, target_doc_id, target_doc_name, resolved_ref, cleaned_query = (
            await self.resolve_document_and_intent(workspace_id, query, recent_history)
        )

        # Build effective semantic search query
        if intent == "CONTEXTUAL_FOLLOWUP" and resolved_ref:
            effective_query = f"{resolved_ref} {cleaned_query}".strip()
        else:
            effective_query = cleaned_query if cleaned_query else query

        raw_chunks: List[Dict[str, Any]] = []

        # 1. If document summary intent with resolved target document, sample across all pages
        if intent == "DOCUMENT_SUMMARY" and target_doc_id:
            raw_chunks = await chunk_repo.get_sampled_chunks_by_document(
                workspace_id=workspace_id,
                document_id=target_doc_id,
                limit=8,
            )

        # 2. If contextual follow-up with resolved reference and document, perform targeted keyword/concept matching
        if intent == "CONTEXTUAL_FOLLOWUP" and resolved_ref and target_doc_id:
            doc_chunks = await chunk_repo.get_sampled_chunks_by_document(
                workspace_id=workspace_id,
                document_id=target_doc_id,
                limit=15,
            )
            ref_words = [w.lower() for w in re.split(r"[\s\:\-\_\,]+", resolved_ref) if len(w) >= 3]
            matching_chunks = []
            for dc in doc_chunks:
                chunk_text_lower = dc["text"].lower()
                chunk_heading_lower = (dc.get("heading") or "").lower()
                matches = sum(1 for rw in ref_words if rw in chunk_text_lower or rw in chunk_heading_lower)
                if matches > 0:
                    matching_chunks.append({**dc, "similarity_score": min(0.98, 0.88 + (0.03 * matches))})

            if matching_chunks:
                raw_chunks = sorted(matching_chunks, key=lambda x: x["similarity_score"], reverse=True)[:5]

        # 3. Fallback to vector search if no chunks retrieved yet
        if not raw_chunks and intent != "WORKSPACE_METADATA":
            query_embedding = await embedding_service.get_query_embedding(effective_query)
            raw_chunks = await chunk_repo.search_similar_chunks(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                top_k=max(self.top_k, 12 if intent == "DOCUMENT_SUMMARY" else self.top_k),
                similarity_threshold=0.35 if intent in ["DOCUMENT_SUMMARY", "CONTEXTUAL_FOLLOWUP"] else self.similarity_threshold,
            )

            # If target doc resolved, prioritize its chunks
            if target_doc_id and raw_chunks:
                doc_filtered = [c for c in raw_chunks if str(c.get("document_id")) == str(target_doc_id)]
                if doc_filtered:
                    raw_chunks = doc_filtered

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
                    document_name=c.get("document_name", target_doc_name or "Workspace Document"),
                    page_number=c.get("page_number", 1),
                    heading=c.get("heading") or "",
                    text=c["text"],
                    similarity_score=c.get("similarity_score", 0.95),
                )
            )

        retrieved_pages = sorted(list(set(c.page_number for c in retrieved)))

        logger.info(
            f"[RAG Diagnostic] workspace_id: '{workspace_id}' | "
            f"conversation_id: '{conversation_id or 'none'}' | "
            f"intent: '{intent}' | "
            f"resolved_document_id: '{target_doc_id or 'none'}' | "
            f"resolved_reference: '{resolved_ref or 'none'}' | "
            f"semantic_query: '{effective_query[:60]}' | "
            f"retrieved_chunk_count: {len(retrieved)} | "
            f"retrieved_pages: {retrieved_pages} | "
            f"Gemini_model: '{settings.gemini_model}'"
        )

        is_grounded = len(retrieved) > 0
        return retrieved, is_grounded, intent, target_doc_id, resolved_ref


retrieval_service = RetrievalService()
