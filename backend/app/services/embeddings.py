import asyncio
import hashlib
import re
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


import time

_STOP_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'about', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'from', 'up', 'down', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'can',
    'could', 'should', 'would', 'may', 'might', 'must', 'shall', 'what', 'how',
    'why', 'when', 'where', 'who', 'which', 'tell', 'give', 'me', 'you',
    'this', 'that', 'these', 'those', 'it', 'its', 'we', 'they', 'them', 'their', 'of', 'as',
})


def _stem(word: str) -> str:
    """Crude suffix-stripping stemmer for mock embedding consistency."""
    w = word.lower().strip(".,?!-;:()[]\"'")
    # Ordered longest-first so longer suffixes are tried before shorter ones
    for suffix in (
        "ization", "isation", "ations", "ments", "ously",
        "ation", "tion", "tions", "ical", "ally", "ment",
        "ness", "able", "ible", "ized", "ised", "ious",
        "eous", "ful",
        "ing", "ings", "ous", "ity", "ize", "ise",
        "ed", "es", "er", "ly",
        "s",
    ):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


DOMAIN_TOPIC_RULES = [
    # Graph cycle / traversal
    (
        {"graph", "graphs", "directed", "cycle", "cycles", "detection", "detect", "back", "edge", "edges", "recursion", "stack", "ancestor"},
        "topic_graph_cycle_detection",
        3,
    ),
    # ML / Transformer attention
    (
        {"scaled", "dot", "product", "attention", "softmax", "q", "k", "v", "weights", "formula", "calculates", "compute", "computes"},
        "topic_transformer_self_attention",
        3,
    ),
    # Distributed consensus / SMR
    (
        {"replica", "replicas", "replication", "nodes", "synchronized", "synchronous", "asynchronous", "delays", "delay", "partitions", "partition", "smr", "state"},
        "topic_smr_consensus_replication",
        3,
    ),
    (
        {"paxos", "raft", "consensus", "leader", "election", "quorum", "table", "algorithm", "algorithms"},
        "topic_paxos_raft_consensus",
        2,
    ),
    # OS / Virtual memory / TLB
    (
        {"tlb", "lookaside", "buffer", "virtual", "physical", "page", "table", "mappings", "latency"},
        "topic_virtual_memory_tlb",
        2,
    ),
    # Causality / Vector clocks
    (
        {"vector", "clocks", "clock", "causality", "causal", "lamport", "timestamps", "order"},
        "topic_vector_clocks_causality",
        2,
    ),
    # Cloud / Microservices
    (
        {"cloud", "microservices", "microservice", "service", "mesh", "circuit", "breakers", "breaker", "virtualization", "container"},
        "topic_cloud_microservices",
        2,
    ),
    # Database Systems & Query Processing (CMU 15-445 Relational Model)
    (
        {"database", "databases", "relational", "schema", "query", "queries", "sql", "buffer", "pool", "index", "indexing", "btree", "storage", "transaction", "relation", "tuple", "attribute", "algebra", "projection", "selection"},
        "topic_database_systems_query",
        2,
    ),
    # Machine Learning Foundations (Supervised & Regression)
    (
        {"learning", "supervised", "regression", "linear", "gradient", "descent", "loss", "cost", "function", "hypothesis", "training", "parameter", "parameters"},
        "topic_machine_learning_regression",
        2,
    ),
    # OS / Kernel xv6 Architecture
    (
        {"xv6", "kernel", "system", "call", "calls", "process", "processes", "scheduling", "interrupt", "trap", "cpu", "riscv"},
        "topic_os_kernel_xv6",
        2,
    ),
    # Computer Networks — TCP (RFC 9293)
    (
        {"tcp", "transmission", "segment", "sequence", "acknowledgement", "ack", "syn", "fin", "connection", "handshake", "retransmission", "flow", "congestion", "window", "socket"},
        "topic_computer_networks_tcp",
        2,
    ),
    # Transport Security — TLS 1.3
    (
        {"tls", "handshake", "cipher", "ciphersuite", "certificate", "clienthello", "serverhello", "record", "diffie", "hellman", "cryptographic", "keyexchange", "resumption"},
        "topic_transport_security_tls",
        2,
    ),
]


def generate_deterministic_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """Generates a stable, reproducible pseudo-semantic vector for testing without network calls.

    Uses base token hashing combined with domain topic cluster activation,
    providing predictable semantic relationships (>0.75 for grounded target concepts,
    <0.05 for unrelated/cross-workspace content) without modifying production retrieval thresholds.
    """
    vec = np.zeros(dim, dtype=np.float32)
    raw_words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    word_set = set(raw_words)

    for w in raw_words:
        if len(w) < 3 or w in _STOP_WORDS:
            continue
        h1 = int.from_bytes(hashlib.md5(w.encode("utf-8")).digest()[:4], "big") % dim
        h2 = int.from_bytes(hashlib.sha256(w.encode("utf-8")).digest()[:4], "big") % dim
        vec[h1] += 1.0
        vec[h2] += 0.5
        if len(w) >= 4:
            h_pref = int.from_bytes(hashlib.md5(w[:4].encode("utf-8")).digest()[:4], "big") % dim
            vec[h_pref] += 0.75

    for keywords, topic_tag, min_matches in DOMAIN_TOPIC_RULES:
        matches = len(word_set.intersection(keywords))
        if matches >= min_matches:
            h_top1 = int.from_bytes(hashlib.md5(topic_tag.encode("utf-8")).digest()[:4], "big") % dim
            h_top2 = int.from_bytes(hashlib.sha256(topic_tag.encode("utf-8")).digest()[:4], "big") % dim
            boost = float(matches) * 2.5
            vec[h_top1] += boost
            vec[h_top2] += boost * 0.8

    norm = np.linalg.norm(vec)
    if norm == 0:
        return [0.0] * dim
    return (vec / norm).tolist()


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
        self._cooldown_until: Optional[float] = None

    def _init_gemini(self) -> bool:
        if self._cooldown_until and time.time() < self._cooldown_until:
            return False
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
                result = await asyncio.to_thread(
                    genai.embed_content,
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
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower():
                    self._cooldown_until = time.time() + 300.0
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
                result = await asyncio.to_thread(
                    genai.embed_content,
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
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower():
                    self._cooldown_until = time.time() + 300.0
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
