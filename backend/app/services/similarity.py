"""
Duplicate detection for generated study material.

Two questions (or flashcards) are duplicates when they test the same fact, even if they are worded
differently: "Under what condition are two complex numbers equal?" and "Which two parts must be
identical for complex numbers to be equal?" ask the same thing. Exact-text checks miss these, so
items are compared by meaning (embedding cosine similarity) and by wording (token overlap).
"""
import math
import re
from typing import Iterable, List, Optional, Sequence

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are", "be", "by", "with", "as",
    "at", "it", "its", "this", "that", "these", "those", "what", "which", "who", "whom", "how", "why",
    "when", "where", "does", "do", "did", "can", "could", "would", "should", "must", "will", "if", "then",
    "than", "their", "there", "they", "them", "from", "into", "about", "following", "true", "statement",
    "best", "describes", "describe", "explain", "correct", "two", "both", "only", "not", "no", "yes",
}

# Meaning-based thresholds (cosine similarity of normalised embeddings)
SEMANTIC_DUPLICATE = 0.90
# Wording-based threshold (Jaccard overlap of content words)
LEXICAL_DUPLICATE = 0.60


def _stem(word: str) -> str:
    for suffix in ("ing", "ers", "er", "ies", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_tokens(text: str) -> set:
    return {_stem(w) for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 1}


def lexical_similarity(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cosine(a: Optional[Sequence[float]], b: Optional[Sequence[float]]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """Embeddings for duplicate checks; None for each text when the embedding service is unavailable."""
    if not texts:
        return []
    try:
        from backend.app.services.embeddings import OFFLINE_EMBEDDING_TAG, embedding_service

        vectors, tag = await embedding_service.embed_documents(texts)
        if tag == OFFLINE_EMBEDDING_TAG:
            # Offline vectors are hashes of the wording, not of the meaning
            return [None] * len(texts)
        return [list(v) for v in vectors]
    except Exception as e:
        logger.info(f"Embeddings unavailable for duplicate checks ({type(e).__name__}); using wording only.")
        return [None] * len(texts)


class DuplicateIndex:
    """Remembers accepted items and tells whether a new item repeats one of them."""

    def __init__(self, semantic_threshold: float = SEMANTIC_DUPLICATE, lexical_threshold: float = LEXICAL_DUPLICATE):
        self.semantic_threshold = semantic_threshold
        self.lexical_threshold = lexical_threshold
        self._texts: List[str] = []
        self._vectors: List[Optional[List[float]]] = []

    def __len__(self) -> int:
        return len(self._texts)

    def add(self, text: str, vector: Optional[Sequence[float]] = None) -> None:
        self._texts.append(text or "")
        self._vectors.append(list(vector) if vector else None)

    def extend(self, texts: Iterable[str], vectors: Optional[Iterable[Optional[Sequence[float]]]] = None) -> None:
        vectors = list(vectors) if vectors is not None else []
        for i, text in enumerate(texts):
            self.add(text, vectors[i] if i < len(vectors) else None)

    def is_duplicate(self, text: str, vector: Optional[Sequence[float]] = None) -> bool:
        for other_text, other_vec in zip(self._texts, self._vectors):
            if vector is not None and other_vec is not None and cosine(vector, other_vec) >= self.semantic_threshold:
                return True
            if lexical_similarity(text, other_text) >= self.lexical_threshold:
                return True
        return False


def question_signature(question_text: str, correct_answer: str) -> str:
    """The text a question is compared on: what it asks plus what its answer is."""
    return f"{question_text.strip()} Answer: {correct_answer.strip()}"
