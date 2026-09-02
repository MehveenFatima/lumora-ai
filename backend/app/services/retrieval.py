from typing import List, Dict, Any, Tuple, Optional
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

    async def resolve_document_and_intent(
        self, workspace_id: str, query: str
    ) -> Tuple[str, Optional[str], Optional[str], str]:
        """
        Resolves query intent and matches any referenced document in the workspace.
        Returns (intent, target_document_id, target_document_name, cleaned_query).
        """
        q_lower = query.lower().strip()
        docs = await document_repo.get_by_workspace(workspace_id)

        target_doc_id = None
        target_doc_name = None

        # 1. Filename matching
        for d in docs:
            fn = d.get("filename", "").lower()
            title = d.get("title", "").lower()
            fn_no_ext = fn.rsplit(".", 1)[0] if "." in fn else fn

            if (
                fn in q_lower
                or fn_no_ext in q_lower
                or (len(fn_no_ext) >= 4 and fn_no_ext.split()[0] in q_lower)
                or title in q_lower
            ):
                target_doc_id = d.get("id")
                target_doc_name = d.get("filename")
                break

        # 2. Anaphoric resolution ("this pdf", "this document", "it")
        if not target_doc_id and len(docs) == 1:
            anaphoric = [
                "this pdf",
                "this document",
                "this source",
                "this file",
                "the document",
                "the pdf",
                "the file",
                "summarize it",
                "explain it",
                "from it",
                "about it",
            ]
            if any(term in q_lower for term in anaphoric) or "summar" in q_lower:
                target_doc_id = docs[0].get("id")
                target_doc_name = docs[0].get("filename")

        # 3. Clean query
        cleaned_query = query
        if target_doc_name:
            import re
            cleaned_query = re.sub(re.escape(target_doc_name), "", cleaned_query, flags=re.IGNORECASE).strip()

        # 4. Intent classification
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
        return intent, target_doc_id, target_doc_name, cleaned_query

    async def retrieve_relevant_chunks(
        self, workspace_id: str, query: str
    ) -> Tuple[List[RetrievedChunk], bool]:
        """
        Retrieves relevant chunks within the specified workspace.
        Supports explicit document reference and document-wide summary aggregation.
        """
        intent, target_doc_id, target_doc_name, cleaned_query = (
            await self.resolve_document_and_intent(workspace_id, query)
        )

        effective_query = cleaned_query if cleaned_query else query
        is_summary = intent == "DOCUMENT_SUMMARY"

        # 1. Generate query embedding
        query_embedding = await embedding_service.get_query_embedding(effective_query)

        # 2. Query vector index
        raw_chunks = await chunk_repo.search_similar_chunks(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=max(self.top_k, 12 if is_summary else self.top_k),
            similarity_threshold=0.40 if is_summary else self.similarity_threshold,
        )

        # If specific document target was resolved, filter to that document
        if target_doc_id and raw_chunks:
            doc_filtered = [c for c in raw_chunks if str(c.get("document_id")) == str(target_doc_id)]
            if doc_filtered:
                raw_chunks = doc_filtered

        if not raw_chunks:
            logger.info(
                f"[RAG Retrieval] No chunks found for workspace '{workspace_id}' (intent={intent})."
            )
            return [], False

        # 3. Deduplicate and construct RetrievedChunk objects
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
                    id=c["id"],
                    document_id=c["document_id"],
                    document_name=c.get("document_name", "Workspace Document"),
                    page_number=c.get("page_number", 1),
                    heading=c.get("heading") or "",
                    text=c["text"],
                    similarity_score=c.get("similarity_score", 0.95),
                )
            )

        is_grounded = len(retrieved) > 0
        return retrieved, is_grounded


retrieval_service = RetrievalService()
