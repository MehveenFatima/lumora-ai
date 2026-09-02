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
        # Excerpt is the first 220 chars of the actual retrieved chunk
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
        self, workspace_id: str, query: str
    ) -> Tuple[List[RetrievedChunk], bool]:
        """
        Retrieves top-k relevant chunks for the query within the specified workspace.
        Returns (chunks, is_grounded).
        """
        # 1. Generate query embedding
        query_embedding = await embedding_service.get_query_embedding(query)

        # 2. Query workspace-filtered vector index
        raw_chunks = await chunk_repo.search_similar_chunks(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=self.top_k,
            similarity_threshold=self.similarity_threshold,
        )

        if not raw_chunks:
            logger.info(
                f"No chunks exceeded threshold {self.similarity_threshold} for query in workspace '{workspace_id}'."
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
                    similarity_score=c["similarity_score"],
                )
            )

        is_grounded = len(retrieved) > 0
        return retrieved, is_grounded


retrieval_service = RetrievalService()
