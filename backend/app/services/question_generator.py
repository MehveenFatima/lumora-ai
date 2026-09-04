"""
LumoraAI - Grounded Adaptive Question Generation Service
Generates validated, deduplicated, diverse diagnostic and targeted multiple-choice questions.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import re
import json
import hashlib
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo

logger = get_logger(__name__)


class NoIndexedDocumentsError(Exception):
    """Raised when an adaptive quiz is requested on a workspace with zero indexed learning materials."""
    pass


class InsufficientContextError(Exception):
    """Raised when indexed materials do not have extractable semantic chunks."""
    pass


def normalize_text_for_comparison(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and compressing whitespace."""
    t = text.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


EVALUATION_STOPWORDS = {
    "according", "to", "regarding", "which", "of", "the", "following", "statements", "statement",
    "is", "are", "correct", "true", "false", "best", "describes", "in", "a", "an", "for", "what",
    "based", "on", "page", "documented", "principle", "property", "established", "operational",
    "definition", "context", "presented", "mechanism", "verified", "characterize", "connection",
    "analysis", "how", "does", "resource", "text", "discussion", "with", "respect",
}


def compute_question_fingerprint(question_text: str, options: Optional[List[Any]] = None) -> str:
    """
    Computes a deterministic normalized fingerprint for question deduplication.
    Combines normalized core question text tokens and sorted option texts.
    """
    q_norm = normalize_text_for_comparison(question_text)
    q_tokens = [w for w in q_norm.split() if w not in EVALUATION_STOPWORDS and len(w) > 2]
    q_key = " ".join(sorted(set(q_tokens)))

    opt_key = ""
    if options:
        opt_texts = [
            normalize_text_for_comparison(opt.get("text", "") if isinstance(opt, dict) else str(opt))
            for opt in options
        ]
        opt_key = "|".join(sorted(opt_texts))

    raw = f"{q_key}::{opt_key}" if opt_key else q_key
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def is_paraphrase_duplicate(text_a: str, text_b: str, threshold: float = 0.70) -> bool:
    """
    Checks if two questions test essentially the same target via token Jaccard similarity.
    """
    tokens_a = set(w for w in normalize_text_for_comparison(text_a).split() if w not in EVALUATION_STOPWORDS and len(w) > 2)
    tokens_b = set(w for w in normalize_text_for_comparison(text_b).split() if w not in EVALUATION_STOPWORDS and len(w) > 2)

    if not tokens_a or not tokens_b:
        return False

    intersection = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    return (intersection / union) >= threshold if union > 0 else False


class GeneratedQuestionData:
    def __init__(
        self,
        topic: str,
        concept: str,
        difficulty: int,
        question_text: str,
        options: List[Dict[str, str]],
        correct_option: str,
        explanation: str,
        document_id: Optional[str] = None,
        document_name: Optional[str] = None,
        page_number: Optional[int] = None,
        source_excerpt: Optional[str] = None,
        fingerprint: Optional[str] = None,
    ):
        self.topic = topic
        self.concept = concept
        self.difficulty = difficulty
        self.question_text = question_text
        self.options = options
        self.correct_option = correct_option
        self.explanation = explanation
        self.document_id = document_id
        self.document_name = document_name
        self.page_number = page_number
        self.source_excerpt = source_excerpt
        self.fingerprint = fingerprint or compute_question_fingerprint(question_text, options)

    def validate(self) -> bool:
        if not self.question_text or len(self.question_text.strip()) < 10:
            return False
        if len(self.options) != 4:
            return False
        keys = [opt.get("key") for opt in self.options]
        if set(keys) != {"A", "B", "C", "D"}:
            return False
        texts = [opt.get("text", "").strip() for opt in self.options]
        if any(not t for t in texts) or len(set(texts)) != 4:
            return False
        if self.correct_option not in {"A", "B", "C", "D"}:
            return False
        if not self.explanation or len(self.explanation.strip()) < 10:
            return False
        if self.difficulty not in {1, 2, 3}:
            return False
        return True


QUESTION_GEN_PROMPT = """You are LumoraAI's pedagogical Assessment Engine.
Your task is to generate high-quality, technically rigorous, multiple-choice questions strictly grounded in the provided [SOURCE CONTEXT].

STRICT RULES & CONSTRAINTS:
1. Grounding: The question and the correct answer MUST be verifiable directly from the provided text. Do not test external facts.
2. Structure:
   - Exactly 4 options labeled A, B, C, D.
   - Exactly ONE option must be correct.
   - The 3 incorrect distractors must be plausible, distinct, and directly related to the concept.
   - Provide a clear, pedagogical explanation explaining why the correct answer is true based on the source text.
3. Difficulty Calibration:
   - 1 (Easy): Direct definition, core invariant, or fundamental mechanism.
   - 2 (Medium): Conceptual trade-off, algorithmic property, state transition, or operational constraint.
   - 3 (Hard): Subtle edge case, multi-step invariant verification, or failure condition deduction.
4. Novelty: Do NOT repeat previously asked questions. Test a distinct conceptual angle.
5. Output Format: Return a JSON array of question objects (or a single question object) with NO markdown wrapping:
[
  {
    "topic": "Topic Name",
    "concept": "Specific Concept Tested",
    "difficulty": 2,
    "question_text": "Clear and precise question?",
    "options": [
      {"key": "A", "text": "Option A text"},
      {"key": "B", "text": "Option B text"},
      {"key": "C", "text": "Option C text"},
      {"key": "D", "text": "Option D text"}
    ],
    "correct_option": "A",
    "explanation": "Detailed grounded explanation."
  }
]
"""


class QuestionGeneratorService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key
        self._model_name = model_name
        self._gemini_configured = False

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key or settings.gemini_api_key

    @property
    def model_name(self) -> str:
        return self._model_name or settings.gemini_model

    def _init_gemini(self) -> bool:
        if self._gemini_configured:
            return True
        key = self.api_key
        if not key:
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            self._gemini_configured = True
            return True
        except Exception as e:
            logger.error(f"Failed to configure Gemini for question generation: {e}")
            return False

    async def get_workspace_chunks(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Fetches and aggregates all indexed chunks across all documents in workspace."""
        docs = await document_repo.list_by_workspace(workspace_id)
        if not docs:
            raise NoIndexedDocumentsError(
                f"No indexed learning materials are available in this workspace '{workspace_id}'. Upload and index a PDF, DOCX, PPTX, or TXT resource before starting an adaptive quiz."
            )

        all_chunks = []
        for d in docs:
            chunks = await chunk_repo.get_chunks_by_document(workspace_id, str(d["id"]))
            if not chunks:
                chunks = await chunk_repo.get_sampled_chunks_by_document(workspace_id, str(d["id"]), limit=50)
            all_chunks.extend(chunks)

        if not all_chunks:
            raise InsufficientContextError(
                f"Workspace '{workspace_id}' has documents but no extractable chunks. Please re-index sources."
            )
        return all_chunks

    def build_concept_inventory_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extracts an inventory of distinct concepts and topics from chunks."""
        concept_map: Dict[str, Dict[str, Any]] = {}

        for idx, c in enumerate(chunks):
            heading = c.get("heading") or c.get("section")
            doc_name = c.get("document_name", "Document")
            text = c.get("text", "")

            # Identify candidate concept names from headings or text
            concept_candidate = None
            if heading and heading.strip() and heading.lower() not in {"general", "introduction", "unit - 1", "chapter 1"}:
                concept_candidate = heading.strip()
            else:
                first_line = text.split("\n")[0].strip() if text else ""
                clean_first_line = re.sub(r"^(?:Page|Unit|Chapter|Section)\s*\d*\s*[:\-–]\s*", "", first_line, flags=re.IGNORECASE).strip()
                if clean_first_line and 3 <= len(clean_first_line) <= 50 and not clean_first_line.lower().startswith("the "):
                    concept_candidate = clean_first_line
                else:
                    m = re.search(r"(?:Chapter|Section|Unit|Topic|Page\s*\d+)?\s*[:\-–]?\s*([A-Z][A-Za-z0-9\s\-]{3,40})(?::|\n|\.|$)", text)
                    if m:
                        concept_candidate = m.group(1).strip()

            if concept_candidate:
                concept_candidate = re.sub(r"^(?:Page|Unit|Chapter|Section)\s*\d*\s*[:\-–]?\s*", "", concept_candidate, flags=re.IGNORECASE).strip()

            if not concept_candidate or len(concept_candidate) < 3 or concept_candidate.lower() in {"page", "unit", "chapter", "section", "topic"}:
                concept_candidate = f"Concept Section {c.get('page_number', idx + 1)}"

            topic_candidate = doc_name.replace(".pdf", "").replace(".txt", "").replace(".docx", "")
            if len(topic_candidate) > 25:
                topic_candidate = topic_candidate[:25]

            if concept_candidate not in concept_map:
                concept_map[concept_candidate] = {
                    "concept": concept_candidate,
                    "topic": topic_candidate,
                    "primary_chunk": c,
                    "chunks": [c],
                }
            else:
                concept_map[concept_candidate]["chunks"].append(c)

        return list(concept_map.values())

    async def extract_available_concepts(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Extracts an inventory of distinct concepts and topics present in the workspace materials.
        """
        chunks = await self.get_workspace_chunks(workspace_id)
        return self.build_concept_inventory_from_chunks(chunks)

    async def generate_candidate_pool(
        self,
        workspace_id: str,
        target_count: int = 5,
        target_concepts: Optional[List[Dict[str, Any]]] = None,
        excluded_fingerprints: Optional[Set[str]] = None,
        excluded_texts: Optional[List[str]] = None,
        preferred_difficulty: int = 2,
        chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[GeneratedQuestionData]:
        """
        Generates an over-sampled candidate pool (>= 10 candidates) and filters for quality,
        grounding, and deduplication.
        """
        excluded_fps = set(excluded_fingerprints or [])
        excluded_qs = list(excluded_texts or [])
        all_chunks = chunks if chunks is not None else await self.get_workspace_chunks(workspace_id)
        concept_inventory = self.build_concept_inventory_from_chunks(all_chunks)

        candidates: List[GeneratedQuestionData] = []
        target_pool_size = max(10, target_count * 2)

        # 1. Determine concept targets to query
        targets_to_query = []
        if target_concepts:
            targets_to_query.extend(target_concepts)
        # Pad with diverse concepts from inventory
        for c_item in concept_inventory:
            if c_item not in targets_to_query:
                targets_to_query.append(c_item)

        # Ensure we have enough targets
        if not targets_to_query:
            targets_to_query = [{"concept": "Core Principles", "topic": "General", "primary_chunk": all_chunks[0], "chunks": all_chunks}]

        # 2. Try Gemini generation in batches if available
        if self._init_gemini():
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel(
                    self.model_name,
                    generation_config={"response_mime_type": "application/json"}
                )

                for target in targets_to_query[:6]:
                    c_name = target.get("concept", "Concept")
                    t_name = target.get("topic", "Topic")
                    chunk = target.get("primary_chunk") or all_chunks[0]
                    context_sample = "\n\n".join([c.get("text", "") for c in target.get("chunks", [chunk])[:3]])

                    prompt = (
                        f"{QUESTION_GEN_PROMPT}\n\n"
                        f"TARGET TOPIC: {t_name}\n"
                        f"TARGET CONCEPT: {c_name}\n"
                        f"DESIRED DIFFICULTY: {preferred_difficulty}\n"
                        f"EXCLUDED QUESTIONS TO AVOID:\n" + "\n".join([f"- {t}" for t in excluded_qs[-5:]]) + "\n\n"
                        f"[SOURCE CONTEXT]:\n{context_sample[:3000]}\n\n"
                        f"Generate 2 distinct, non-overlapping JSON question objects for this concept:"
                    )

                    res = model.generate_content(prompt)
                    if res and res.text:
                        raw_json = res.text.strip()
                        if raw_json.startswith("```"):
                            raw_json = re.sub(r"^```(?:json)?\n?", "", raw_json)
                            raw_json = re.sub(r"\n?```$", "", raw_json)
                        
                        items = json.loads(raw_json)
                        if isinstance(items, dict):
                            items = [items]

                        for item in items:
                            q_data = GeneratedQuestionData(
                                topic=item.get("topic") or t_name,
                                concept=item.get("concept") or c_name,
                                difficulty=int(item.get("difficulty", preferred_difficulty)),
                                question_text=item.get("question_text", ""),
                                options=item.get("options", []),
                                correct_option=item.get("correct_option", "A"),
                                explanation=item.get("explanation", ""),
                                document_id=str(chunk.get("document_id")),
                                document_name=chunk.get("document_name"),
                                page_number=chunk.get("page_number", 1),
                                source_excerpt=chunk.get("text", "")[:250],
                            )
                            if q_data.validate():
                                fp = q_data.fingerprint
                                is_dupe = (
                                    fp in excluded_fps
                                    or any(fp == c.fingerprint for c in candidates)
                                    or any(is_paraphrase_duplicate(q_data.question_text, c.question_text) for c in candidates)
                                    or any(is_paraphrase_duplicate(q_data.question_text, eq) for eq in excluded_qs)
                                )
                                if not is_dupe:
                                    candidates.append(q_data)

                    if len(candidates) >= target_pool_size:
                        break
            except Exception as e:
                logger.warning(f"Gemini candidate pool generation warning: {e}. Supplementing with deterministic synthesis.")

        # 3. Deterministic Grounded Synthesis (Ensures 100% diversity without repetition)
        # Distribute across available chunks and distinct sentences
        chunk_count = len(all_chunks)
        step = max(1, chunk_count // target_pool_size)

        for i in range(target_pool_size * 4):
            if len(candidates) >= target_pool_size:
                break

            chunk_idx = (i * step) % chunk_count
            chunk = all_chunks[chunk_idx]
            
            # Synthesize distinct question from chunk
            synth_q = self._synthesize_diverse_question(
                chunk=chunk,
                chunk_index=chunk_idx,
                iteration_seed=i,
                target_difficulty=preferred_difficulty,
                excluded_texts=excluded_qs + [c.question_text for c in candidates],
            )
            if synth_q and synth_q.validate():
                fp = synth_q.fingerprint
                if fp not in excluded_fps and not any(fp == c.fingerprint for c in candidates):
                    if (
                        not any(is_paraphrase_duplicate(synth_q.question_text, c.question_text) for c in candidates)
                        and not any(is_paraphrase_duplicate(synth_q.question_text, eq) for eq in excluded_qs)
                    ):
                        candidates.append(synth_q)

        return candidates

    def _synthesize_diverse_question(
        self,
        chunk: Dict[str, Any],
        chunk_index: int,
        iteration_seed: int,
        target_difficulty: int,
        excluded_texts: List[str],
    ) -> Optional[GeneratedQuestionData]:
        """
        Synthesizes a distinct, strictly grounded question rotating across sentences, concepts, and templates.
        """
        text = chunk.get("text", "")
        doc_name = chunk.get("document_name", "Workspace Document")
        page_num = chunk.get("page_number", 1)
        heading = chunk.get("heading") or "Core Topic"

        # Split into substantial sentences
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
        if not raw_sentences:
            return None

        # Pick sentence deterministically based on iteration seed
        sentence_idx = (iteration_seed + chunk_index) % len(raw_sentences)
        target_sentence = raw_sentences[sentence_idx]

        # Clean target sentence from prefixes and extract subject concept
        clean_sentence = re.sub(r"^(?:Page|Unit|Chapter|Section)\s*\d*\s*[:\-–]?\s*", "", target_sentence, flags=re.IGNORECASE).strip()
        first_line_clean = clean_sentence.split("\n")[0].strip()
        concept_match = re.search(r"([A-Z][a-z0-9]+(?:[ \t]+[A-Z][a-z0-9]+){1,3})", first_line_clean)
        if not concept_match:
            concept_match = re.search(r"([A-Z][a-z0-9]+)", first_line_clean)
        concept = concept_match.group(1).strip() if concept_match else heading
        concept = re.sub(r"\s+", " ", concept).strip()
        if concept.lower() in {"page", "unit", "chapter", "section", "topic"} and heading:
            concept = heading

        snippet = re.sub(r"\s+", " ", clean_sentence)[:75].rstrip(".,; ")

        # Question template variants incorporating page and sentence snippet
        templates = [
            f"Based on {doc_name} (Page {page_num}) regarding {concept} ('{snippet}...'), which statement accurately captures the documented principle?",
            f"According to {doc_name} on Page {page_num} concerning {concept} ('{snippet}...'), what key invariant or property is established?",
            f"Which of the following correctly reflects the operational definition of {concept} described on Page {page_num} ('{snippet}...')?",
            f"In the context of {concept} on Page {page_num} ('{snippet}...'), what mechanism is verified?",
            f"How does {doc_name} characterize {concept} on Page {page_num} with respect to '{snippet}...'?",
        ]
        q_template = templates[iteration_seed % len(templates)]

        # Check if identical question text exists in exclusions
        if any(normalize_text_for_comparison(q_template) == normalize_text_for_comparison(eq) for eq in excluded_texts):
            q_template = f"Regarding {concept} on Page {page_num} of {doc_name} ('{snippet}...'), what primary property is detailed?"

        # Construct distinct distractors
        distractor_variations = [
            [
                f"The text specifies that {concept} executes strictly in constant O(1) time without any prerequisite initialization.",
                f"The documentation confirms that {concept} is solely utilized for unindexed sequential text streams.",
                f"The material indicates that {concept} operates inversely to standard protocol specifications.",
            ],
            [
                f"The resource proves that {concept} requires unbounded auxiliary stack memory during traversal.",
                f"The analysis states that {concept} can only be applied when data elements are statically pre-sorted.",
                f"The documentation establishes that {concept} replaces all deterministic guarantees with random sampling.",
            ],
            [
                f"The passage states that {concept} terminates only when all boundary conditions are intentionally violated.",
                f"The author defines {concept} as an exclusively hardware-implemented network primitive.",
                f"The reference notes that {concept} disables synchronization mechanisms across concurrent threads.",
            ],
        ]
        chosen_distractors = distractor_variations[(iteration_seed + page_num) % len(distractor_variations)]

        # Rotate correct answer position
        pos_keys = ["A", "B", "C", "D"]
        correct_key = pos_keys[iteration_seed % 4]
        
        options = []
        d_idx = 0
        for k in pos_keys:
            if k == correct_key:
                options.append({"key": k, "text": target_sentence})
            else:
                options.append({"key": k, "text": chosen_distractors[d_idx % len(chosen_distractors)]})
                d_idx += 1

        diff = max(1, min(3, (iteration_seed % 3) + 1 if target_difficulty == 2 else target_difficulty))

        return GeneratedQuestionData(
            topic=heading,
            concept=concept,
            difficulty=diff,
            question_text=q_template,
            options=options,
            correct_option=correct_key,
            explanation=f"Based directly on {doc_name} (Page {page_num}): '{target_sentence}'",
            document_id=str(chunk.get("document_id")),
            document_name=doc_name,
            page_number=page_num,
            source_excerpt=text[:250],
        )

    async def generate_question(
        self,
        workspace_id: str,
        topic: Optional[str] = None,
        concept: Optional[str] = None,
        target_difficulty: int = 2,
        excluded_question_texts: Optional[List[str]] = None,
        excluded_fingerprints: Optional[Set[str]] = None,
    ) -> GeneratedQuestionData:
        """
        Generates a single distinct question by leveraging the candidate pool.
        """
        target_concepts = [{"concept": concept, "topic": topic or "General"}] if concept else None
        candidates = await self.generate_candidate_pool(
            workspace_id=workspace_id,
            target_count=1,
            target_concepts=target_concepts,
            excluded_fingerprints=excluded_fingerprints,
            excluded_texts=excluded_question_texts,
            preferred_difficulty=target_difficulty,
        )
        if not candidates:
            raise InsufficientContextError("Could not generate a unique grounded question without duplicating previous questions.")
        return candidates[0]


question_generator_service = QuestionGeneratorService()
