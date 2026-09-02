import hashlib
from typing import List, Optional
import numpy as np
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


def l2_normalize(vector: List[float]) -> List[float]:
    arr = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return vector
    return (arr / norm).tolist()


def generate_deterministic_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """Generates a stable, reproducible pseudo-semantic vector for testing without network calls."""
    # Compute sha256 hash
    hasher = hashlib.sha256()
    hasher.update(text.encode("utf-8"))
    seed = int.from_bytes(hasher.digest()[:8], "big")
    
    rng = np.random.RandomState(seed % (2**32))
    vec = rng.randn(dim).astype(np.float32)
    
    # Inject word-based features into the vector to provide realistic keyword similarity
    words = text.lower().split()
    for idx, w in enumerate(words[:20]):
        word_hash = int.from_bytes(hashlib.md5(w.encode("utf-8")).digest()[:4], "big") % dim
        vec[word_hash] += 2.5 / (idx + 1)
        
    return l2_normalize(vec.tolist())


class EmbeddingService:
    def __init__(
        self,
        api_key: Optional[str] = settings.gemini_api_key,
        model_name: str = settings.gemini_embedding_model,
        dimension: int = settings.embedding_dimensions,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension
        self._gemini_client_initialized = False

    def _init_gemini(self) -> bool:
        if self._gemini_client_initialized:
            return True
        if not self.api_key:
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._gemini_client_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to configure Google Generative AI: {e}")
            return False

    async def get_embedding(self, text: str) -> List[float]:
        """Generates an embedding vector for a single text."""
        clean_text = text.replace("\n", " ").strip()
        if not clean_text:
            clean_text = "empty"

        if self._init_gemini():
            try:
                import google.generativeai as genai
                result = genai.embed_content(
                    model=self.model_name,
                    content=clean_text,
                    task_type="retrieval_document",
                )
                raw_emb = result["embedding"]
                # Truncate / pad to 768 dimensions if necessary
                if len(raw_emb) > self.dimension:
                    raw_emb = raw_emb[: self.dimension]
                elif len(raw_emb) < self.dimension:
                    raw_emb = raw_emb + [0.0] * (self.dimension - len(raw_emb))
                return l2_normalize(raw_emb)
            except Exception as e:
                logger.warning(
                    f"Gemini API embedding call failed ({e}). Using deterministic embedding fallback."
                )

        return generate_deterministic_mock_embedding(clean_text, self.dimension)

    async def get_query_embedding(self, query: str) -> List[float]:
        """Generates an embedding vector for a query with task_type='retrieval_query'."""
        clean_query = query.replace("\n", " ").strip()
        if not clean_query:
            clean_query = "query"

        if self._init_gemini():
            try:
                import google.generativeai as genai
                result = genai.embed_content(
                    model=self.model_name,
                    content=clean_query,
                    task_type="retrieval_query",
                )
                raw_emb = result["embedding"]
                if len(raw_emb) > self.dimension:
                    raw_emb = raw_emb[: self.dimension]
                elif len(raw_emb) < self.dimension:
                    raw_emb = raw_emb + [0.0] * (self.dimension - len(raw_emb))
                return l2_normalize(raw_emb)
            except Exception as e:
                logger.warning(
                    f"Gemini API query embedding call failed ({e}). Using deterministic embedding fallback."
                )

        return generate_deterministic_mock_embedding(clean_query, self.dimension)

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of chunks."""
        embeddings = []
        for t in texts:
            emb = await self.get_embedding(t)
            embeddings.append(emb)
        return embeddings


embedding_service = EmbeddingService()
