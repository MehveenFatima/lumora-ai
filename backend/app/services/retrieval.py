from typing import List, Dict, Any, Tuple
from backend.app.repositories.chunks import chunk_repo
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

    def is_summary_query(self, query: str) -> bool:
        q = query.lower()
        summary_keywords = [
            "summar",
            "what are the concepts",
            "what concepts",
            "overview",
            "main topic",
            "all concepts",
            "syllabus",
            "tell me about this",
            "explain this pdf",
            "what is this document about",
            "key points",
            "table of contents",
        ]
        return any(k in q for k in summary_keywords)

    async def retrieve_relevant_chunks(
        self, workspace_id: str, query: str
    ) -> Tuple[List[RetrievedChunk], bool]:
        """
        Retrieves top-k relevant chunks for the query within the specified workspace.
        Supports document-wide summary intent by sampling representative chunks.
        Returns (chunks, is_grounded).
        """
        is_summary = self.is_summary_query(query)

        # 1. Generate query embedding
        query_embedding = await embedding_service.get_query_embedding(query)

        # 2. Query workspace-filtered vector index
        raw_chunks = await chunk_repo.search_similar_chunks(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=max(self.top_k, 12 if is_summary else self.top_k),
            similarity_threshold=0.40 if is_summary else self.similarity_threshold,
        )

        if not raw_chunks:
            logger.info(
                f"No chunks found for query in workspace '{workspace_id}'."
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
