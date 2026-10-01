"""
LumoraAI - Grounded Adaptive Question Generation Service
=========================================================
Generates pedagogically sound, technically rigorous, deduplicated, diverse
multiple-choice questions strictly grounded in workspace materials.

PIPELINE:
RAG retrieval -> source context -> concept extraction -> assessment target selection
-> question generation (independent assessment) -> quality validation & anti-leakage
-> deduplication -> final question
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import re
import json
import hashlib
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.repositories.documents import document_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.services.question_quality_validator import (
    question_quality_validator,
    ValidationResult,
    QUESTION_TYPES,
)

logger = get_logger(__name__)


class NoIndexedDocumentsError(Exception):
    """Raised when an adaptive quiz is requested on a workspace with zero indexed learning materials."""
    pass


class InsufficientContextError(Exception):
    """Raised when indexed materials do not have extractable semantic chunks."""
    pass


def normalize_text_for_comparison(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and compressing whitespace."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


EVALUATION_STOPWORDS = {
    "according", "to", "regarding", "which", "of", "the", "following", "statements", "statement",
    "is", "are", "correct", "true", "false", "best", "describes", "in", "a", "an", "for", "what",
    "based", "on", "page", "documented", "principle", "property", "established", "operational",
    "definition", "context", "presented", "mechanism", "verified", "characterize", "connection",
    "analysis", "how", "does", "resource", "text", "discussion", "with", "respect", "primary",
    "purpose", "role", "function", "ensure", "prevent", "unauthorized", "state", "modification",
    "communication", "system", "design", "allocated", "architectural", "invariant", "enforced",
    "advance", "accomplish", "responsibility", "guarantee", "formally", "computational",
    "efficiency", "tradeoff", "trade-off", "associated", "runtime", "scaling", "behavior",
    "bound", "constraint", "applies", "establishment", "task", "executed", "serve", "overall",
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
        question_type: str = "conceptual",
        document_id: Optional[str] = None,
        document_name: Optional[str] = None,
        page_number: Optional[int] = None,
        source_excerpt: Optional[str] = None,
        quality_score: float = 1.0,
        leakage_score: float = 0.0,
        fingerprint: Optional[str] = None,
    ):
        self.topic = topic
        self.concept = concept
        self.difficulty = difficulty
        self.question_text = question_text
        self.options = options
        self.correct_option = correct_option
        self.explanation = explanation
        self.question_type = question_type
        self.document_id = document_id
        self.document_name = document_name
        self.page_number = page_number
        self.source_excerpt = source_excerpt
        self.quality_score = quality_score
        self.leakage_score = leakage_score
        self.fingerprint = fingerprint or compute_question_fingerprint(question_text, options)

    def validate(self) -> bool:
        """
        Runs full validation including structural sanity, distractor checks,
        and the anti-leakage validator.
        """
        if not self.question_text or len(self.question_text.strip()) < 15:
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

        # Run anti-leakage quality validator
        val_res = question_quality_validator.validate_question(
            question_text=self.question_text,
            options=self.options,
            correct_option=self.correct_option,
            concept=self.concept,
            topic=self.topic,
            source_excerpt=self.source_excerpt,
            document_name=self.document_name,
            page_number=self.page_number,
            question_type=self.question_type,
            difficulty=self.difficulty,
        )

        self.quality_score = val_res.quality_score
        self.leakage_score = val_res.leakage_score

        return val_res.is_valid


QUESTION_GEN_PROMPT = """You are LumoraAI's pedagogical Assessment Engine.
Your task is to generate high-quality, technically rigorous, multiple-choice questions strictly grounded in the provided [SOURCE CONTEXT].

CRITICAL ANTI-LEAKAGE & PEDAGOGICAL RULES:
1. NO ANSWER LEAKAGE:
   - The question stem must NEVER quote, summarize, or embed the correct answer or its key explanatory clause.
   - The question stem must NEVER reproduce the verbatim text of any answer choice.
   - The learner must have to UNDERSTAND the source concept to select the correct answer; the answer must not be trivially obvious from the stem wording.
2. NO CITATION METADATA IN QUESTION STEMS:
   - NEVER include filenames (e.g. "document.pdf", "notes.docx") or page numbers ("Page 37", "on page 5") in the question text.
   - NEVER start questions with "According to [Document] on Page X says...".
   - Citations belong exclusively in the citation metadata, NOT in the assessment stem.
3. NO RAW SOURCE DUMPING:
   - Do NOT dump raw source passages, code dumps, or copy-pasted textbook sentences into the question stem.
   - Instead, formulate an independent assessment asking about: purpose, architectural role, mechanism, invariants, preconditions, behavior, or complexity.
4. QUESTION TYPE DIVERSITY:
   - Assign a valid "question_type" chosen from:
     ["conceptual", "comparison", "application", "scenario", "reasoning", "trace_output", "interpretation", "edge_case", "complexity_analysis"]
   - Do not ask only "What is X?". Vary cognitive demands.
5. OPTION BALANCE & DISTRACTOR QUALITY:
   - All 4 options (A, B, C, D) MUST be approximately equal in length, grammatical complexity, and domain tone.
   - The correct answer must NOT be conspicuously longer, more detailed, or uniquely formatted.
   - The 3 distractors must be plausible, coherent in the same domain, and mutually distinct.
6. DIFFICULTY CALIBRATION:
   - 1 (Easy): Core conceptual definition, primary objective, fundamental mechanism.
   - 2 (Medium): State transition, algorithmic property, trade-off, or operational constraint.
   - 3 (Hard): Boundary condition, subtle failure state deduction, multi-step reasoning.

OUTPUT FORMAT: Return a JSON array of question objects with NO markdown wrapping:
[
  {
    "topic": "Topic Name",
    "concept": "Specific Concept Tested",
    "difficulty": 2,
    "question_type": "conceptual",
    "question_text": "Clear, independent question without citation leaks or answer clues?",
    "options": [
      {"key": "A", "text": "Option A text of balanced length"},
      {"key": "B", "text": "Option B text of balanced length"},
      {"key": "C", "text": "Option C text of balanced length"},
      {"key": "D", "text": "Option D text of balanced length"}
    ],
    "correct_option": "A",
    "explanation": "Clear explanation of why the correct option is true based on the concept."
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
        """Extracts an inventory of distinct concepts and topics present in the workspace materials."""
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
        anti-leakage, grounding, and deduplication.
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
            for tc in target_concepts:
                if isinstance(tc, dict):
                    targets_to_query.append(tc)
                elif isinstance(tc, str):
                    targets_to_query.append({"concept": tc, "topic": "General"})
        for c_item in concept_inventory:
            if c_item not in targets_to_query:
                targets_to_query.append(c_item)

        if not targets_to_query:
            targets_to_query = [{"concept": "Core Principles", "topic": "General", "primary_chunk": all_chunks[0], "chunks": all_chunks}]

        # 2. Try Multi-Model AI Gateway Generation (Primary: OpenRouter Qwen 3.8 27B, Fallback: Gemini 3.8 Flash)
        try:
            from backend.app.ai.gateway import ai_gateway
            from backend.app.ai.types import AIRequest, TaskType

            for target in targets_to_query[:6]:
                c_name = target.get("concept", "Concept")
                t_name = target.get("topic", "Topic")
                chunk = target.get("primary_chunk") or all_chunks[0]
                context_sample = "\n\n".join([(c.get("content") or c.get("text") or "") for c in target.get("chunks", [chunk])[:3]])

                prompt = (
                    f"{QUESTION_GEN_PROMPT}\n\n"
                    f"TARGET TOPIC: {t_name}\n"
                    f"TARGET CONCEPT: {c_name}\n"
                    f"DESIRED DIFFICULTY: {preferred_difficulty}\n"
                    f"EXCLUDED QUESTIONS TO AVOID:\n" + "\n".join([f"- {t}" for t in excluded_qs[-5:]]) + "\n\n"
                    f"[SOURCE CONTEXT]:\n{context_sample[:3000]}\n\n"
                    f"Generate 2 distinct, non-overlapping JSON question objects for this concept. Return a JSON object with a 'questions' array containing the question objects."
                )

                ai_req = AIRequest(
                    prompt=prompt,
                    system_prompt="You are an expert assessment designer. Respond strictly in valid JSON format with a top-level 'questions' array of question objects.",
                    task_type=TaskType.QUIZ,
                    temperature=0.3,
                )

                ai_res = await ai_gateway.generate_structured(ai_req)
                if ai_res and ai_res.structured_data:
                    data = ai_res.structured_data
                    if isinstance(data, dict):
                        items = data.get("questions") or data.get("items") or [data]
                    elif isinstance(data, list):
                        items = data
                    else:
                        items = []

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        q_data = GeneratedQuestionData(
                            topic=item.get("topic") or t_name,
                            concept=item.get("concept") or c_name,
                            difficulty=int(item.get("difficulty", preferred_difficulty)),
                            question_type=item.get("question_type") or "conceptual",
                            question_text=item.get("question_text", ""),
                            options=item.get("options", []),
                            correct_option=item.get("correct_option", "A"),
                            explanation=item.get("explanation", ""),
                            document_id=str(chunk.get("document_id")),
                            document_name=chunk.get("document_name"),
                            page_number=chunk.get("page_number", 1),
                            source_excerpt=(chunk.get("content") or chunk.get("text") or "")[:300],
                        )
                        # Strict quality validation & anti-leakage check
                        if q_data.validate():
                            fp = q_data.fingerprint
                            is_dupe = (
                                fp in excluded_fps
                                or any(fp == c.fingerprint for c in candidates)
                                or any(q_data.question_text.strip().lower() == c.question_text.strip().lower() for c in candidates)
                                or any(c.concept.lower() == q_data.concept.lower() and is_paraphrase_duplicate(q_data.question_text, c.question_text) for c in candidates)
                                or any(is_paraphrase_duplicate(q_data.question_text, eq) for eq in excluded_qs)
                            )
                            if not is_dupe:
                                candidates.append(q_data)

                if len(candidates) >= target_pool_size:
                    break
                if not ai_res or not ai_res.structured_data:
                    logger.info("AI Gateway did not return candidates (provider unavailable or cooldown). Breaking early to deterministic synthesis.")
                    break
        except Exception as e:
            logger.warning(f"AI Gateway candidate pool generation notice: {e}. Supplementing with deterministic synthesis.")


        # 3. Deterministic Grounded Synthesis (100% Leakage-Free & Distinct)
        chunk_count = len(all_chunks)
        step = max(1, chunk_count // target_pool_size)

        for i in range(target_pool_size * 6):
            if len(candidates) >= target_pool_size:
                break

            chunk_idx = (i * step) % chunk_count
            chunk = all_chunks[chunk_idx]

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
                        not any(synth_q.question_text.strip().lower() == c.question_text.strip().lower() for c in candidates)
                        and not any(c.concept.lower() == synth_q.concept.lower() and is_paraphrase_duplicate(synth_q.question_text, c.question_text) for c in candidates)
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
        """Synthesizes a high-quality, independent assessment question:

        - Filters out raw code fences, Markdown tables, shebangs, and HTML.
        - NEVER copies citation metadata (document name, page number) into the stem.
        - NEVER dumps raw source snippets into the stem.
        - NEVER leaks the correct answer into the stem.
        - Generates balanced, same-domain distractors.
        - Validates through the production-grade MCQ gate before returning.
        """
        raw_text = chunk.get("content") or chunk.get("text") or ""
        doc_name = chunk.get("document_name", "Workspace Document")
        page_num = chunk.get("page_number", 1)
        heading = (chunk.get("heading") or "").strip()

        # 1. Clean raw text: Strip code blocks, Markdown tables, shebangs, HTML
        clean_lines = []
        in_code_block = False
        for line in raw_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if "|" in line_str:
                continue  # Skip Markdown table lines
            if line_str.startswith("#") or line_str.startswith("=begin") or line_str.startswith("=end"):
                continue
            if any(bad in line_str.lower() for bad in ["gem install", "bundle exec", "print \"", "require '", "import ", "<table", "<tr>", "<td>", "extracted table", "statement "]):
                continue
            clean_lines.append(line_str)

        text = " ".join(clean_lines)

        # 2. Extract substantial conceptual sentences
        raw_sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
            if len(s.strip()) > 30
            and not any(ext in s.lower() for ext in [".pdf", ".docx", ".pptx", ".txt"])
            and not any(bad in s.lower() for bad in [
                "code:", "syntax:", "handling form", "procfile", "extracted table", "statement ",
                "here's how", "here is how", "how to", "in this section", "this section covers",
                "for example", "example:", "let's look", "consider the following", "the following code",
                "the following example", "step 1", "step 2", "click on", "run the command", "open the file",
                "as shown in", "refer to", "see section", "see chapter", "tutorial", "chapter "
            ])
            and "|" not in s
            and "=" not in s
            and "[" not in s and "]" not in s
            and "{" not in s and "}" not in s
            and "`" not in s
            and not s.strip().startswith("#")
        ]
        if not raw_sentences:
            return None

        # 3. Extract and validate concept candidate
        BAD_CONCEPT_PATTERNS = [
            "foreword", "acknowledgment", "figure", "table", "chart", "diagram",
            "internet engineering", "task force", "rescorla", "standards track",
            "rfc 8446", "rfc", "august 2018", "fall 2012", "fall", "spring", "lecture notes",
            "course notes", "notes", "copyright", "all rights reserved", "contents",
            "author", "authors", "mit 6.", "cs229", "stanford", "university",
            "page", "unit", "chapter", "section", "after", "before", "int n", "return",
            "void", "struct", "char", "p2 figure", "figure 2", "figure 1", "figure 3",
            "underboss", "consigliere", "boss", "carlo", "tony", "baffo",
            "updates", "affecting", "austin", "clements", "russ", "andrew ng", "curino",
            "september", "description", "rfc 9293", "andy pavlo", "15-445", "cmu 15-445", "lecture 01"
        ]

        def _is_valid_concept(c_str: str) -> bool:
            if not c_str or len(c_str) < 3:
                return False
            c_low = c_str.lower().strip()
            if any(bad in c_low for bad in BAD_CONCEPT_PATTERNS):
                return False
            if not re.match(r"^[A-Za-z]", c_str):
                return False
            if any(c_low.startswith(p) for p in ["part ", "chapter ", "section ", "unit ", "page ", "figure ", "table ", "a ", "the ", "this ", "in ", "on ", "to "]):
                return False
            if c_low in ("a file", "file", "int n", "after", "before", "c files", "user programs", "adam belay", "russ cox"):
                return False
            return True

        concept = None
        if heading and heading.lower() not in ("core principle", "general", "workspace document", "introduction", "overview", "summary"):
            clean_head = re.sub(r"^(?:Page|Unit|Chapter|Section|Example)\s*\d*\s*[:\-–]?\s*", "", heading, flags=re.IGNORECASE).strip()
            clean_head = re.sub(r"^(?:Basics\s+of|Introduction\s+to|Overview\s+of|Fundamentals\s+of|Guide\s+to|Notes\s+on|Chapter\s+on|Section\s+on|Discussion\s+on|Summary\s+of)\s+", "", clean_head, flags=re.IGNORECASE).strip()
            clean_head = re.sub(r"[:\-–|].*$", "", clean_head).strip()
            clean_head = re.sub(r"[^\w\s]", "", clean_head).strip()
            if _is_valid_concept(clean_head):
                concept = clean_head

        if not concept:
            # Look in text for substantive technical capitalized concepts
            cand_phrases = re.findall(r"\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){1,2})\b", text)
            for cp in cand_phrases:
                cp_clean = re.sub(r"[^\w\s]", "", cp).strip()
                if _is_valid_concept(cp_clean):
                    concept = cp_clean
                    break

        if not concept:
            ctx_lower = (text + " " + doc_name).lower()
            if "tcp" in ctx_lower or "rfc 9293" in ctx_lower:
                concept = "Transmission Control Protocol"
            elif "tls" in ctx_lower or "handshake" in ctx_lower:
                concept = "TLS Handshake Protocol"
            elif "xv6" in ctx_lower or "kernel" in ctx_lower:
                concept = "Kernel Page Tables"
            elif "database" in ctx_lower or "relational" in ctx_lower or "sql" in ctx_lower:
                concept = "Relational Model & Schema"
            elif "regression" in ctx_lower or "gradient" in ctx_lower:
                concept = "Gradient Descent Optimization"
            else:
                return None

        # Clean concept
        concept = re.sub(r"[:\-–|].*$", "", concept).strip()
        concept = re.sub(r"^(?:Basics\s+of|Introduction\s+to|Overview\s+of|Fundamentals\s+of|Guide\s+to|Notes\s+on)\s+", "", concept, flags=re.IGNORECASE).strip()
        if not _is_valid_concept(concept):
            return None

        # 4. Identify domain for same-domain distractors
        combined_context = (text + " " + doc_name + " " + heading + " " + concept).lower()
        if any(k in combined_context for k in ["ruby", "tkroot", "tkbutton", "tklabel", "tkinter", "webrick", "cgi script", "cookie", "gem ", "rake", "irb"]):
            domain = "ruby_scripting"
        elif any(k in combined_context for k in ["tcp", "transmission control", "rfc 9293", "segment", "sequence number", "acknowledgement", "syn", "fin", "congestion", "retransmission", "sliding window"]):
            domain = "tcp_networks"
        elif any(k in combined_context for k in ["tls", "handshake", "cipher", "certificate", "cryptograph", "encryption", "message authentication code", "hmac", "mac tag", "integrity", "confidentiality"]) or ("ssl" in combined_context and not any(r in combined_context for r in ["ruby", "script", "cgi", "tk"])):
            domain = "ssl_crypto"
        elif any(k in combined_context for k in ["virtual memory", "paging", "page table", "tlb", "thrashing", "deadlock", "process", "kernel", "operating system", "demand paging"]):
            domain = "os_systems"
        elif any(k in combined_context for k in ["database", "relational", "sql", "buffer pool", "schema", "b+ tree", "query execution", "index", "storage manager", "dbms", "mit 6.830", "cmu", "15-445", "algebra", "tuple", "attribute"]):
            domain = "db_systems"
        elif any(k in combined_context for k in ["machine learning", "regression", "gradient descent", "loss function", "cost function", "supervised", "hypothesis", "training set", "cs229"]):
            domain = "ml_systems"
        elif any(k in combined_context for k in ["tree", "graph", "queue", "stack", "sort", "search", "bfs", "dfs", "binary", "heap", "hash", "dsa", "complexity", "o("]):
            domain = "dsa"
        elif any(k in combined_context for k in ["consensus", "paxos", "raft", "quorum", "replication", "replica", "causality", "vector clock", "smr", "distributed"]):
            domain = "dist_sys"
        elif any(k in combined_context for k in ["microservice", "service mesh", "circuit breaker", "container", "virtualization", "cloud"]):
            domain = "cloud"
        else:
            domain = "general"

        # Determine question type and templates
        if domain == "ruby_scripting":
            q_type = "application"
            stem_templates = [
                f"What core architectural responsibility is fulfilled by {concept} in application development?",
                f"How does {concept} coordinate operational logic and component execution?",
                f"Which programmatic role is fundamentally assigned to {concept}?",
            ]
        elif domain == "tcp_networks":
            q_type = "reasoning"
            stem_templates = [
                f"What core transport reliability or flow-control responsibility is fulfilled by {concept} in TCP?",
                f"How does {concept} coordinate state transitions and reliable byte-stream transmission in TCP?",
                f"Which protocol invariant or connection guarantee is strictly enforced by {concept}?",
                f"During transmission or connection management, how does {concept} maintain endpoint synchronization?",
            ]
        elif domain == "ssl_crypto":
            q_type = "reasoning"
            stem_templates = [
                f"Through what primary mechanism does {concept} ensure cryptographic integrity and confidentiality?",
                f"What security guarantee is formally established by {concept}?",
                f"How does {concept} prevent unauthorized state modification in protocol communication?",
                f"In secure communications, what foundational objective is achieved by {concept}?",
                f"Which cryptographic property or verification rule is strictly enforced by {concept}?",
                f"How does {concept} mitigate adversarial tampering or unauthorized observation?",
            ]
        elif domain == "db_systems":
            q_type = "conceptual"
            stem_templates = [
                f"What primary storage or query-execution role is fulfilled by {concept} in relational database architecture?",
                f"Which relational invariant or storage property is maintained by {concept}?",
                f"How does {concept} coordinate data access between in-memory buffers and persistent storage?",
            ]
        elif domain == "ml_systems":
            q_type = "conceptual"
            stem_templates = [
                f"What primary optimization or learning role is fulfilled by {concept} in supervised model training?",
                f"Which mathematical invariant or convergence property is governed by {concept}?",
                f"How does {concept} coordinate parameter updates to minimize the empirical cost function?",
            ]
        elif domain == "dist_sys":
            q_type = "application"
            stem_templates = [
                f"During distributed coordination, what operational role is fulfilled by {concept}?",
                f"Under network partitions or delays, how does {concept} maintain consistent state?",
                f"What invariant guarantee is enforced by {concept} across participating nodes?",
            ]
        elif domain == "os_systems":
            q_type = "conceptual"
            stem_templates = [
                f"What primary memory-management role is fulfilled by {concept} in system architecture?",
                f"Which architectural invariant or address-translation property is maintained by {concept}?",
                f"How does {concept} coordinate state between virtual address spaces and physical resources?",
            ]
        elif domain == "dsa":
            q_type = "conceptual"
            stem_templates = [
                f"Which structural invariant or traversal property underpins {concept}?",
                f"What core data-organization principle is maintained by {concept}?",
                f"Through what internal mechanism does {concept} manage element relationships?",
            ]
        else:
            q_type = "conceptual"
            stem_templates = [
                f"What primary operational purpose does {concept} serve in the system architecture?",
                f"Which architectural property or operational invariant is guaranteed by {concept}?",
                f"Through what mechanism does {concept} accomplish its documented function?",
            ]

        q_stem = stem_templates[iteration_seed % len(stem_templates)]

        # 5. Domain-coherent distractors (NEVER cross-domain, NEVER table garbage)
        if domain == "ruby_scripting":
            distractor_pools = [
                [
                    "Bypasses runtime execution flow to render output without initializing necessary object state.",
                    "Directly reinterprets byte-level instructions without dispatching standard event handlers.",
                    "Dispatches unmanaged asynchronous callbacks without binding to application scope.",
                ],
                [
                    "Forces immediate thread termination when an unbound event handler is invoked.",
                    "Isolates application state in global memory without hierarchical object scoping.",
                    "Overwrites default method dispatch tables to prevent polymorphic runtime resolution.",
                ],
            ]
        elif domain == "tcp_networks":
            distractor_pools = [
                [
                    "Transmits unsequenced datagrams asynchronously without establishing initial sequence number synchronization.",
                    "Suppresses packet retransmission timers, allowing lost segments to be silently discarded without acknowledgement.",
                    "Disables flow control windows, permitting sender transmission to overflow receiver buffer capacity unconditionally.",
                ],
                [
                    "Bypasses the three-way handshake to transmit application payload before sequence synchronization completes.",
                    "Sets congestion window sizes to unbounded maximum values regardless of packet drop signals.",
                    "Eliminates sequence numbering from packet headers, preventing the receiver from reassembling in-order byte streams.",
                ],
            ]
        elif domain == "ssl_crypto":
            distractor_pools = [
                [
                    "Permits unauthenticated client endpoints to bypass message digest calculation during renegotiation.",
                    "Transmits master session keys in unencrypted format during the initial client hello exchange.",
                    "Restricts cryptographic verification exclusively to asymmetric public key encryption without message integrity.",
                ],
                [
                    "Terminates active sessions unconditionally whenever asymmetric key exchange is initiated.",
                    "Forces all communicating endpoints to revert to unencrypted legacy protocol baselines.",
                    "Disables record-layer sequence numbering, leaving messages vulnerable to replay attacks.",
                ],
            ]
        elif domain == "os_systems":
            distractor_pools = [
                [
                    "Allocates physical frames statically at compile-time without virtual address translation.",
                    "Suppresses hardware page-fault interrupts to prevent kernel trap handler invocation.",
                    "Flushes all resident memory pages to auxiliary disk storage upon every context switch.",
                ],
                [
                    "Prevents page replacement algorithms from identifying referenced frames in memory.",
                    "Eliminates multi-level page table hierarchies by enforcing contiguous physical allocation.",
                    "Disables translation lookaside caching, forcing memory references to traverse unmapped addresses.",
                ],
            ]
        elif domain == "db_systems":
            distractor_pools = [
                [
                    "Bypasses the buffer pool manager to write uncommitted transaction updates directly to raw disk sectors.",
                    "Suppresses write-ahead logging protocols, permitting asynchronous dirty page writes without crash recovery.",
                    "Replaces indexed B+ tree lookups with unconstrained sequential table scans for every primary key query.",
                ],
                [
                    "Forces continuous synchronous disk flushes for every single read operation regardless of buffer cache hits.",
                    "Eliminates relational schema constraints to permit arbitrary untyped tuples across all table pages.",
                    "Disables query optimizer cost models, forcing arbitrary nested loop join orders across relational tables.",
                ],
            ]
        elif domain == "ml_systems":
            distractor_pools = [
                [
                    "Sets model parameter weights to static predefined constants without computing loss gradients.",
                    "Increases parameter step size unconditionally upon diverging loss without checking gradient signs.",
                    "Disables the cost function evaluation, preventing gradient updates from converging toward minimal error.",
                ],
                [
                    "Replaces convex error optimization with arbitrary random parameter assignments during backpropagation.",
                    "Enforces non-differentiable step boundaries across continuous feature spaces without regularization.",
                    "Suppresses iterative gradient updates, assuming the initial randomized hypothesis parameters are optimal.",
                ],
            ]
        elif domain == "dsa":
            distractor_pools = [
                [
                    "Maintains element ordering strictly by appending newly inserted keys to the tail of an unindexed array.",
                    "Traverses deeper branches unconditionally without maintaining a visited state record.",
                    "Guarantees logarithmic height solely when input elements are inserted in strictly sorted order.",
                ],
                [
                    "Executes in strict constant O(1) time complexity regardless of input dimension or partition depth.",
                    "Requires unbounded exponential O(2^N) auxiliary stack memory during standard execution.",
                    "Degrades to quadratic O(N^2) overhead even when data elements are statically pre-sorted.",
                ],
            ]
        elif domain == "dist_sys":
            distractor_pools = [
                [
                    "Requires unanimous agreement across all participating cluster nodes rather than a majority quorum.",
                    "Permits follower nodes to commit unverified state changes independently of leader coordination.",
                    "Relies on synchronized physical wall-clock timestamps rather than monotonic logical causality.",
                ],
                [
                    "Suspends log replication unconditionally whenever a single follower experiences network latency.",
                    "Elects new cluster leaders without verifying term numbers or log entry completeness.",
                    "Discards uncommitted state transitions during network partitions without safety validation.",
                ],
            ]
        elif domain == "cloud":
            distractor_pools = [
                [
                    "Routes all inter-service communication through unmonitored point-to-point static socket connections.",
                    "Bypasses upstream health checks by forwarding requests continuously to timing-out services.",
                    "Isolates container workloads at the hypervisor level rather than utilizing OS kernel namespaces.",
                ],
            ]
        else:
            distractor_pools = [
                [
                    "Replaces deterministic algorithmic guarantees with unconstrained heuristic approximations.",
                    "Disables defensive boundary assertions to maximize throughput without input validation.",
                    "Suppresses exception dispatching to enforce non-terminating background execution.",
                ],
            ]

        chosen_distractors = distractor_pools[(iteration_seed + page_num) % len(distractor_pools)]

        # Rotate correct key among A, B, C, D
        pos_keys = ["A", "B", "C", "D"]
        correct_key = pos_keys[iteration_seed % 4]

        diff = max(1, min(3, (iteration_seed % 3) + 1 if target_difficulty == 2 else target_difficulty))

        # 6. Try sentences deterministically to find a valid synthesis
        start_idx = (iteration_seed + chunk_index) % len(raw_sentences)
        for offset in range(len(raw_sentences)):
            sentence_idx = (start_idx + offset) % len(raw_sentences)
            target_sentence = raw_sentences[sentence_idx]

            # Clean sentence from chapter/page headings
            clean_sentence = re.sub(r"^(?:Page|Unit|Chapter|Section|Example)\s*\d*\s*[:\-–]?\s*", "", target_sentence, flags=re.IGNORECASE).strip()

            clean_ans = clean_sentence
            clean_ans = re.sub(r"[A-Za-z0-9_\-\s]+\.(?:pdf|docx|pptx|txt)\s*[:\-–]?\s*", "", clean_ans, flags=re.IGNORECASE).strip()
            clean_ans = re.sub(r"^(?:page|example|unit|chapter|section)\s*\d*\s*[:\-–]?\s*", "", clean_ans, flags=re.IGNORECASE).strip()
            clean_ans = re.sub(r"[\[\]\{\}\<\>\=\`]", "", clean_ans).strip()
            clean_ans = re.sub(r"[^\x20-\x7E]", "", clean_ans).strip()
            clean_ans = re.sub(r"^(?:Tutorial|Guide|Notes|Example|Exercise|Step\s*\d*|Case\s*\d*)\s*[:\-–]?\s*", "", clean_ans, flags=re.IGNORECASE).strip()

            if any(bad_w in clean_ans.lower() for bad_w in ["underboss", "consigliere", "shifezza", "baffo", "tony", "carlo", "lungo"]):
                continue

            if len(clean_ans) > 130:
                first_clause = re.split(r"[,;.]", clean_ans)[0].strip()
                if len(first_clause) >= 40:
                    clean_ans = first_clause + "."
                else:
                    clean_ans = clean_ans[:115].rsplit(" ", 1)[0] + "."

            clean_ans = clean_ans[0].upper() + clean_ans[1:] if clean_ans else ""
            if clean_ans and not clean_ans.endswith("."):
                clean_ans += "."

            if len(clean_ans) < 35 or "|" in clean_ans or "=" in clean_ans or "[" in clean_ans or "]" in clean_ans:
                continue

            has_inst, _ = question_quality_validator.check_instructional_or_heading_answer(clean_ans)
            if has_inst:
                continue

            has_bad_concept, _ = question_quality_validator.check_concept_naming_quality(concept, q_stem)
            if has_bad_concept:
                continue

            dummy_opts = [{"key": "A", "text": clean_ans}, {"key": "B", "text": "distractor"}, {"key": "C", "text": "distractor"}, {"key": "D", "text": "distractor"}]
            has_incompat, _ = question_quality_validator.check_semantic_stem_answer_compatibility(q_stem, clean_ans, dummy_opts, concept)
            if has_incompat:
                continue

            options = []
            d_idx = 0
            for k in pos_keys:
                if k == correct_key:
                    options.append({"key": k, "text": clean_ans})
                else:
                    options.append({"key": k, "text": chosen_distractors[d_idx % len(chosen_distractors)]})
                    d_idx += 1

            q_obj = GeneratedQuestionData(
                topic=heading or "Core Principle",
                concept=concept,
                difficulty=diff,
                question_type=q_type,
                question_text=q_stem,
                options=options,
                correct_option=correct_key,
                explanation=f"Based on {heading or 'curriculum'} ({concept}): {clean_ans}",
                document_id=str(chunk.get("document_id")),
                document_name=doc_name,
                page_number=page_num,
                source_excerpt=text[:300],
            )

            # Validate through production gate
            if q_obj.validate():
                return q_obj

        return None

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
