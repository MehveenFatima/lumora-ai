"""
Topic map: the subject-matter concepts each document teaches.

Quiz questions and flashcards are generated per concept from this map, so they cover the real
subject of the notes (for example "Modulus of a complex number") instead of whatever sentence a
chunk happened to start with. Slides about the lesson itself ("Independent Practice", "Learning
Objectives", "Exit Ticket") are not concepts and are left out.

With an AI provider the map is written by the model from the whole document. Without one (local
development and tests) it falls back to the document's headings.
"""
import asyncio
import re
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.concepts import concept_repo
from backend.app.repositories.documents import document_repo
from backend.app.services.similarity import lexical_similarity
from backend.app.services.text_cleanup import clean_label, clean_study_text, split_sentences

logger = get_logger(__name__)

# Characters of document text per extraction request, and the most requests per document
SECTION_CHARS = 14000
MAX_SECTION_CHARS = 30000
MAX_SECTIONS_PER_DOCUMENT = 8
MAX_CONCEPTS_PER_DOCUMENT = 40
EXTRACTION_TIMEOUT_SECONDS = 120
EXTRACTION_CONCURRENCY = 3
EXTRACTION_ATTEMPTS = 3
EXTRACTION_RETRY_SECONDS = 30

# Headings and slide titles that describe the lesson rather than the subject. Phrases match
# anywhere in a heading; single words only when they are the whole heading ("Reflection" alone is a
# lesson activity, "Reflection of light" is physics).
META_PHRASES = re.compile(
    r"\b("
    r"independent\s+practice|guided\s+practice|practice\s+(?:time|session|set|sheet|problems?|questions?|exercises?)|"
    r"class\s*work|home\s*work|worksheet|warm[\s\-]?up|exit\s+ticket|do\s+now|bell\s*ringer|"
    r"learning\s+(?:objectives?|outcomes?|goals?|targets?)|lesson\s+(?:objectives?|plan|overview|summary|goals?)|"
    r"course\s+(?:objectives?|outline|information|overview|outcomes?)|success\s+criteria|answer\s+key|"
    r"check\s+your\s+(?:understanding|answers?)|review\s+questions?|self[\s\-]?assessment|"
    r"try\s+(?:it\s+yourself|these|this\s+one)|your\s+turn|group\s+(?:work|activity|discussion)|class\s+activity|"
    r"activity\s+\d+|exercise\s+\d+|discussion\s+questions?|wrap[\s\-]?up|table\s+of\s+contents|"
    r"further\s+reading|about\s+(?:the\s+)?authors?|all\s+rights\s+reserved|thank\s+you|any\s+questions|"
    r"today\s+we\s+will|we\s+will\s+learn|in\s+this\s+(?:lesson|lecture|video)"
    r")\b",
    re.IGNORECASE,
)
META_HEADINGS = {
    "agenda", "objectives", "objective", "outcomes", "goals", "contents", "references", "bibliography",
    "acknowledgements", "acknowledgments", "preface", "foreword", "syllabus", "homework", "assignment",
    "assignments", "exercises", "exercise", "practice", "activity", "activities", "reflection", "recap",
    "review", "quiz", "questions", "discussion", "summary", "conclusion", "thank you", "copyright",
}

EXTRACTION_PROMPT = """You are building a study map of a student's course material.

From the MATERIAL below, list the distinct subject-matter concepts a student has to learn.

What counts as a concept:
- A piece of subject knowledge: a definition, rule, property, theorem, formula, method, process,
  mechanism, classification or comparison. Name it precisely, for example "Equality of complex
  numbers", "Modulus of a complex number", "TCP three-way handshake", "Normalisation (2NF)".
- Exercises and worked examples are not concepts. Use them as key points of the concept they practise
  (for example "Worked example: if z = 3 + 4i then |z| = 5").

Leave out everything about the lesson rather than the subject: titles, agendas, learning objectives,
instructions to students ("Independent Practice", "Try these", "Exit ticket", "Homework", "Group work"),
teacher notes, slide numbers, author names, references and administrative text.

For each concept return:
- topic: the chapter or unit-level subject it belongs to (2-5 words)
- concept: its precise name (2-7 words)
- summary: 1-2 sentences explaining it in plain language
- key_points: 2-6 precise facts, rules, formulas, conditions or worked-example results stated in the
  material. Keep formulas and numbers exactly (write maths in plain text, e.g. "|z| = sqrt(a^2 + b^2)").
- source_pages: the page numbers (from the [p.N] markers) where it is taught

Rules: use only what the material states; merge duplicates so every concept is distinct; order the
concepts as they appear in the material.

Return JSON: {"concepts": [{"topic": "...", "concept": "...", "summary": "...", "key_points": ["..."], "source_pages": [1]}]}
"""


def is_meta_content(label: Optional[str]) -> bool:
    """True for headings that describe the lesson (activities, objectives, admin), not the subject."""
    if not label:
        return False
    bare = re.sub(r"^[\W\d_]+|[\W\d_]+$", "", label.lower()).strip()
    bare = re.sub(r"\s+", " ", bare)
    return bare in META_HEADINGS or bool(META_PHRASES.search(label))


def normalize_concept_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def _chunk_text(chunk: Dict[str, Any]) -> str:
    return (chunk.get("text") or chunk.get("content") or "").replace("\x00", " ").strip()


def _page(chunk: Dict[str, Any]) -> int:
    try:
        return int(chunk.get("page_number") or 1)
    except (TypeError, ValueError):
        return 1


def build_sections(chunks: List[Dict[str, Any]]) -> List[str]:
    """Splits a document into page-marked sections that each fit one extraction request."""
    total = sum(len(_chunk_text(c)) for c in chunks)
    size = min(MAX_SECTION_CHARS, max(SECTION_CHARS, total // MAX_SECTIONS_PER_DOCUMENT + 1))
    sections: List[str] = []
    current: List[str] = []
    length = 0
    last_page = None
    for c in chunks:
        text = _chunk_text(c)
        if not text:
            continue
        page = _page(c)
        piece = (f"[p.{page}] " if page != last_page else "") + text
        last_page = page
        if length + len(piece) > size and current:
            sections.append("\n".join(current))
            current, length = [], 0
            piece = f"[p.{page}] " + text
        current.append(piece)
        length += len(piece) + 1
    if current:
        sections.append("\n".join(current))
    if len(sections) > MAX_SECTIONS_PER_DOCUMENT:
        step = len(sections) / MAX_SECTIONS_PER_DOCUMENT
        sections = [sections[int(i * step)] for i in range(MAX_SECTIONS_PER_DOCUMENT)]
    return sections


def _clean_concept(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    concept = re.sub(r"\s+", " ", str(item.get("concept") or "")).strip(" .:-")
    if len(concept) < 3 or is_meta_content(concept) or not re.search(r"[A-Za-z]{3,}", concept):
        return None
    topic = re.sub(r"\s+", " ", str(item.get("topic") or "")).strip(" .:-") or concept
    key_points = [
        re.sub(r"\s+", " ", str(p)).strip()
        for p in (item.get("key_points") or [])
        if isinstance(p, (str, int, float)) and len(str(p).strip()) >= 8
    ]
    pages = []
    for p in item.get("source_pages") or []:
        try:
            pages.append(int(p))
        except (TypeError, ValueError):
            continue
    return {
        "topic": topic[:120],
        "concept": concept[:160],
        "summary": re.sub(r"\s+", " ", str(item.get("summary") or "")).strip(),
        "key_points": key_points[:8],
        "source_pages": sorted(set(pages)),
    }


def merge_concepts(concepts: List[Dict[str, Any]], limit: int = MAX_CONCEPTS_PER_DOCUMENT) -> List[Dict[str, Any]]:
    """Joins concepts that name the same idea (sections can overlap) and caps the map's size."""
    merged: List[Dict[str, Any]] = []
    for c in concepts:
        name = normalize_concept_name(c["concept"])
        match = next(
            (
                m for m in merged
                if normalize_concept_name(m["concept"]) == name
                or lexical_similarity(m["concept"], c["concept"]) >= 0.8
            ),
            None,
        )
        if match:
            for point in c.get("key_points") or []:
                if all(lexical_similarity(point, p) < 0.7 for p in match["key_points"]):
                    match["key_points"].append(point)
            match["key_points"] = match["key_points"][:8]
            match["source_pages"] = sorted(set(match["source_pages"]) | set(c.get("source_pages") or []))
            if not match.get("summary") and c.get("summary"):
                match["summary"] = c["summary"]
            continue
        merged.append({**c, "key_points": list(c.get("key_points") or []), "source_pages": list(c.get("source_pages") or [])})
    return merged[:limit]


def heuristic_concepts(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Offline topic map from the document's headings, skipping lesson/admin slides."""
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for c in chunks:
        heading = clean_label(c.get("heading") or c.get("section"))
        if not heading or is_meta_content(heading):
            continue
        if heading.lower() in {"general", "introduction", "overview", "summary", "notes"}:
            continue
        key = normalize_concept_name(heading)
        if key not in groups:
            groups[key] = {"concept": heading, "texts": [], "pages": set()}
            order.append(key)
        groups[key]["texts"].append(clean_study_text(_chunk_text(c), c.get("heading")))
        groups[key]["pages"].add(_page(c))

    doc_topic = None
    if chunks:
        name = str(chunks[0].get("document_name") or "")
        doc_topic = re.sub(r"\.(pdf|docx?|pptx?|txt)$", "", name, flags=re.IGNORECASE).strip()[:60] or None

    concepts = []
    for key in order:
        g = groups[key]
        sentences = [s for s in split_sentences(" ".join(g["texts"])) if 30 <= len(s) <= 300]
        if not sentences:
            continue
        concepts.append({
            "topic": doc_topic or g["concept"],
            "concept": g["concept"],
            "summary": sentences[0],
            "key_points": sentences[1:5],
            "source_pages": sorted(g["pages"]),
        })
    return merge_concepts(concepts)


class ConceptMapService:
    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}

    @staticmethod
    def ai_available() -> bool:
        from backend.app.ai.gateway import ai_gateway
        from backend.app.ai.types import TaskType

        return ai_gateway.has_configured_provider(TaskType.QUIZ)

    async def _extract_section(self, section: str, document_name: str) -> List[Dict[str, Any]]:
        from backend.app.ai.gateway import ai_gateway
        from backend.app.ai.types import AIRequest, TaskType

        request = AIRequest(
            prompt=f"{EXTRACTION_PROMPT}\nDOCUMENT: {document_name}\n\nMATERIAL:\n{section}",
            system_prompt="You are an expert teacher who maps course material into concepts. Respond only with valid JSON.",
            task_type=TaskType.QUIZ,
            temperature=0.1,
            model=settings.gemini_generation_model,
        )
        response = await asyncio.wait_for(ai_gateway.generate_structured(request), timeout=EXTRACTION_TIMEOUT_SECONDS)
        data = getattr(response, "structured_data", None)
        items = data.get("concepts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        return [c for c in (_clean_concept(i) for i in items if isinstance(i, dict)) if c]

    async def extract(self, chunks: List[Dict[str, Any]], document_name: str) -> List[Dict[str, Any]]:
        """AI topic map of one document; raises when every extraction request failed."""
        sections = build_sections(chunks)
        if not sections:
            return []
        semaphore = asyncio.Semaphore(EXTRACTION_CONCURRENCY)

        async def run(section: str):
            async with semaphore:
                for attempt in range(EXTRACTION_ATTEMPTS):
                    try:
                        return await self._extract_section(section, document_name)
                    except Exception as e:
                        logger.warning(
                            f"Topic map extraction failed for a section of '{document_name}' "
                            f"(attempt {attempt + 1}/{EXTRACTION_ATTEMPTS}): {type(e).__name__}: {e}"
                        )
                        if attempt + 1 < EXTRACTION_ATTEMPTS:
                            # Long enough for a rate-limited provider to leave its cooldown
                            await asyncio.sleep(EXTRACTION_RETRY_SECONDS * (attempt + 1))
                return None

        results = await asyncio.gather(*(run(s) for s in sections))
        if all(r is None for r in results):
            raise RuntimeError(f"Topic map extraction failed for '{document_name}'.")
        found = [c for r in results if r for c in r]
        return merge_concepts(found)

    async def build_for_document(
        self,
        workspace_id: str,
        document_id: str,
        document_name: Optional[str] = None,
        chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if chunks is None:
            chunks = await chunk_repo.get_chunks_by_document(workspace_id, str(document_id))
        if not chunks:
            return []
        name = document_name or chunks[0].get("document_name") or "Document"

        concepts: List[Dict[str, Any]] = []
        method = "heuristic"
        if self.ai_available():
            try:
                concepts = await self.extract(chunks, name)
                method = "ai"
            except Exception as e:
                logger.warning(f"Using the heading-based topic map for '{name}': {e}")
        if not concepts:
            concepts, method = heuristic_concepts(chunks), "heuristic"
        if not concepts:
            return []
        saved = await concept_repo.replace_for_document(workspace_id, str(document_id), name, concepts, method=method)
        logger.info(f"Topic map for '{name}': {len(saved)} concepts ({method}).")
        return saved

    async def ensure_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Builds the topic map of every document that has none yet (or only a heading-based one when AI is now available)."""
        lock = self._locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            existing = await concept_repo.list_by_workspace(workspace_id)
            ai = self.ai_available()
            mapped = {
                str(c["document_id"]) for c in existing
                if c.get("document_id") and (c.get("method") == "ai" or not ai)
            }
            docs = await document_repo.list_by_workspace(workspace_id)
            changed = False
            for d in docs:
                doc_id = str(d["id"])
                if doc_id in mapped:
                    continue
                if (d.get("status") or "ready") != "ready":
                    continue
                await self.build_for_document(workspace_id, doc_id, d.get("filename") or d.get("title"))
                changed = True
            return await concept_repo.list_by_workspace(workspace_id) if changed else existing

    async def get_workspace_concepts(self, workspace_id: str) -> List[Dict[str, Any]]:
        return await concept_repo.list_by_workspace(workspace_id)

    @staticmethod
    def source_text(concept: Dict[str, Any], chunks: List[Dict[str, Any]], limit: int = 7000) -> str:
        """The passages of the concept's document that teach it (by page, else by wording)."""
        doc_chunks = [c for c in chunks if str(c.get("document_id")) == str(concept.get("document_id"))] or chunks
        pages = set(concept.get("source_pages") or [])
        picked = [c for c in doc_chunks if _page(c) in pages] if pages else []
        if not picked:
            name = concept.get("concept", "")
            scored = sorted(
                doc_chunks,
                key=lambda c: lexical_similarity(name + " " + " ".join(concept.get("key_points") or []), _chunk_text(c)),
                reverse=True,
            )
            picked = scored[:4]
        parts, total = [], 0
        for c in picked:
            text = _chunk_text(c)
            if total + len(text) > limit:
                text = text[: max(0, limit - total)]
            if text:
                parts.append(f"[p.{_page(c)}] {text}")
                total += len(text)
            if total >= limit:
                break
        return "\n".join(parts)


concept_map_service = ConceptMapService()
