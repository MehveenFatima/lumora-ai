"""
Question bank: exam-quality multiple-choice questions written per concept of the topic map.

Every question goes through four gates before a learner sees it:
1. Generation from the concept's key points and the passages that teach it, with a prompt that asks
   for understanding and application (worked problems for maths and other problem-solving subjects),
   never for the wording of one sentence.
2. The structural and anti-leakage validator (question_quality_validator).
3. A second AI pass that re-checks the answer key (re-computing calculations), rejects ambiguous
   questions, weak distractors and questions about the lesson instead of the subject.
4. Duplicate detection by meaning against every question already in the bank, so the same fact is
   never asked twice in different words.

The bank is filled in the background after a document is indexed and topped up as questions are
served; quizzes are assembled from it, adapted to the learner's mastery and target difficulty.
"""
import asyncio
import math
import random
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.repositories.quizzes import quiz_repo
from backend.app.services.concept_map import concept_map_service, normalize_concept_name
from backend.app.services.question_generator import GeneratedQuestionData, compute_question_fingerprint
from backend.app.services.similarity import (
    DuplicateIndex,
    embed_texts,
    lexical_similarity,
    question_signature,
)

logger = get_logger(__name__)

GENERATOR_TAG = "concept_v2"
# Questions kept per concept in the bank, and the most ever written for one concept
TARGET_PER_CONCEPT = 6
REFILL_BELOW = 3
MAX_PER_CONCEPT = 24
GENERATION_TIMEOUT_SECONDS = 90
# Tries per concept before giving up for this run (the next trigger fills the rest)
GENERATION_ATTEMPTS = 5
BUILD_CONCURRENCY = 2

QUESTION_TYPES_FOR_PROMPT = (
    "conceptual, application, calculation, comparison, scenario, reasoning, edge_case, interpretation, "
    "trace_output, complexity_analysis"
)

QUESTION_PROMPT = """You write exam-quality multiple-choice questions for a student, the way a strong teacher builds a practice test.

CONCEPT: {concept}
TOPIC: {topic}
SUMMARY: {summary}
KEY POINTS:
{key_points}

SOURCE MATERIAL (the student's notes):
{source}

Write {count} questions on this concept with these difficulties, in order: {difficulties}.

What makes a good question:
- It tests understanding of the subject, not recognition of a sentence. A student who only memorised
  the wording of the notes must not be able to answer by matching words.
- Every question tests a different idea or skill within the concept. Never ask the same fact twice in
  different words.
- Use varied forms: apply the idea to a new example, work out a result, compare two ideas, spot which
  statement or case satisfies a rule, predict what changes if a condition changes, find the mistake in
  a piece of reasoning.
- For mathematics, physics, chemistry, statistics, accounting, programming and other problem-solving
  subjects, at least half of the questions must be worked problems with specific values, for example
  "If z1 = 2 + 3i and z2 = 1 - i, what is z1 * z2?". The wrong options are the results of typical
  mistakes (a sign error, the wrong formula, forgetting that i^2 = -1).
- Difficulty 1: one direct step. Difficulty 2: two steps, or telling two close ideas apart.
  Difficulty 3: multi-step reasoning, an edge case, or a common misconception.
- Ask only about the subject. Never ask about the lesson, slides, activities, instructions, the
  teacher, the document, page numbers or "the text".
- The question must not contain or hint at its answer, and must be answerable from the material.
- Already in the question bank (do not repeat or rephrase these):
{avoid}

Options:
- Exactly 4 options, exactly one of them correct beyond doubt.
- Wrong options are plausible to a student who half-understands the concept, belong to the same
  concept, and are clearly wrong to a student who understands it. No "all of the above",
  "none of the above", "both A and B", true/false or yes/no options.
- All options have the same form and similar length (all numbers, all expressions, or all short
  statements). Each option is at least 4 characters (write "z = 5", not "5").
- Write maths in plain text: i, sqrt(x), x^2, pi, theta, |z| for a modulus.

Explanation: 1-3 sentences that show why the answer is right (for a calculation, the working) and,
when useful, the mistake behind the most tempting wrong option.

question_type is one of: {types}.

Return JSON:
{{"questions": [{{"difficulty": 1, "question_type": "calculation", "question_text": "...?",
"options": [{{"key": "A", "text": "..."}}, {{"key": "B", "text": "..."}}, {{"key": "C", "text": "..."}}, {{"key": "D", "text": "..."}}],
"correct_option": "B", "explanation": "...", "source_page": 3}}]}}
"""

REVIEW_PROMPT = """You are checking multiple-choice questions written for a student from the source material below.

SOURCE MATERIAL:
{source}

QUESTIONS:
{questions}

Check every question:
1. correct: the marked answer is right according to the material. For any calculation, work it out
   yourself step by step before deciding.
2. single: no other option is also correct or defensible.
3. subject: it is about the subject matter, not about the lesson, activities, slides or the document.
4. worthwhile: it tests understanding or application; the stem does not give the answer away and it
   cannot be answered by matching words from the notes.
5. distractors: every wrong option is plausible and belongs to the same concept.

Return JSON: {{"reviews": [{{"index": 0, "keep": true, "reason": "short reason"}}]}}
Keep a question only if it passes all five checks.
"""

_KEYS = ["A", "B", "C", "D"]


def _difficulty_plan(count: int, preferred: Optional[int] = None) -> List[int]:
    if preferred in (1, 2, 3):
        neighbour = 2 if preferred != 2 else 3
        plan = [preferred, preferred, neighbour]
    else:
        plan = [1, 1, 2, 2, 3, 3]
    while len(plan) < count:
        plan += plan
    return sorted(plan[:count])


def _normalize_options(raw: Any) -> List[str]:
    """Option texts in order from the shapes models return ({key,text} list, strings, or a dict)."""
    if isinstance(raw, dict):
        return [str(raw.get(k, "")).strip() for k in _KEYS if k in raw]
    texts = []
    for o in raw or []:
        if isinstance(o, dict):
            texts.append(str(o.get("text", "")).strip())
        else:
            texts.append(re.sub(r"^[A-D][\).:]\s*", "", str(o)).strip())
    return texts


def _correct_index(raw_correct: Any, texts: List[str]) -> Optional[int]:
    value = str(raw_correct or "").strip()
    if value[:1].upper() in _KEYS and (len(value) == 1 or value[1:2] in (")", ".", ":", " ")):
        idx = _KEYS.index(value[:1].upper())
        return idx if idx < len(texts) else None
    for i, t in enumerate(texts):
        if value and value.lower() == t.lower():
            return i
    return None


def build_question(
    item: Dict[str, Any],
    concept: Dict[str, Any],
    source_excerpt: str,
    default_difficulty: int = 2,
) -> Optional[GeneratedQuestionData]:
    """Turns one model-written item into a validated question (options shuffled), or None."""
    texts = _normalize_options(item.get("options"))
    if len(texts) != 4 or any(not t for t in texts):
        return None
    correct = _correct_index(item.get("correct_option"), texts)
    if correct is None:
        return None
    try:
        difficulty = int(item.get("difficulty", default_difficulty))
    except (TypeError, ValueError):
        difficulty = default_difficulty
    difficulty = min(3, max(1, difficulty))

    question_text = re.sub(r"\s+", " ", str(item.get("question_text") or "")).strip()
    # Models put the correct answer first more often than chance; place it at random
    order = list(range(4))
    random.Random(question_text).shuffle(order)
    options = [{"key": _KEYS[pos], "text": texts[i]} for pos, i in enumerate(order)]
    correct_key = _KEYS[order.index(correct)]

    pages = concept.get("source_pages") or []
    try:
        page = int(item.get("source_page") or (pages[0] if pages else 1))
    except (TypeError, ValueError):
        page = pages[0] if pages else 1

    q_type = str(item.get("question_type") or "conceptual").strip().lower()
    q = GeneratedQuestionData(
        topic=concept.get("topic") or concept.get("concept") or "General",
        concept=concept.get("concept") or "Concept",
        difficulty=difficulty,
        question_text=question_text,
        options=options,
        correct_option=correct_key,
        explanation=re.sub(r"\s+", " ", str(item.get("explanation") or "")).strip(),
        question_type=q_type,
        document_id=str(concept["document_id"]) if concept.get("document_id") else None,
        document_name=concept.get("document_name"),
        page_number=page,
        source_excerpt=source_excerpt[:400],
    )
    if not q.validate():
        return None
    return q


async def _call(prompt: str, system_prompt: str, temperature: float) -> Any:
    from backend.app.ai.gateway import ai_gateway
    from backend.app.ai.types import AIRequest, TaskType

    request = AIRequest(
        prompt=prompt,
        system_prompt=system_prompt,
        task_type=TaskType.QUIZ,
        temperature=temperature,
        model=settings.gemini_generation_model,
    )
    response = await ai_gateway.generate_structured(request)
    return getattr(response, "structured_data", None) if response else None


def _items(data: Any, key: str) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        found = data.get(key) or data.get("items") or []
    elif isinstance(data, list):
        found = data
    else:
        found = []
    return [i for i in found if isinstance(i, dict)]


async def review_questions(questions: List[GeneratedQuestionData], source: str) -> List[GeneratedQuestionData]:
    """Second AI pass: keeps only questions whose key, uniqueness, subject and distractors check out."""
    if not questions or not settings.study_material_review:
        return questions
    listing = "\n\n".join(
        f"[{i}] {q.question_text}\n"
        + "\n".join(f"  {o['key']}. {o['text']}" for o in q.options)
        + f"\n  Marked answer: {q.correct_option}\n  Explanation: {q.explanation}"
        for i, q in enumerate(questions)
    )
    try:
        data = await _call(
            REVIEW_PROMPT.format(source=source[:6000], questions=listing),
            "You are a meticulous examiner who verifies answer keys. Respond only with valid JSON.",
            0.0,
        )
    except Exception as e:
        # The validator already passed these; a failed review must not discard the batch
        logger.info(f"Question review unavailable ({type(e).__name__}); keeping validated questions.")
        return questions
    reviews = _items(data, "reviews")
    if not reviews:
        return questions
    rejected = set()
    for r in reviews:
        try:
            idx = int(r.get("index"))
        except (TypeError, ValueError):
            continue
        keep = r.get("keep")
        if keep is False or str(keep).lower() == "false":
            rejected.add(idx)
    if rejected:
        logger.info(f"Question review rejected {len(rejected)} of {len(questions)} questions.")
    return [q for i, q in enumerate(questions) if i not in rejected]


async def generate_for_concept(
    concept: Dict[str, Any],
    source: str,
    count: int,
    duplicates: DuplicateIndex,
    excluded_fingerprints: Optional[Set[str]] = None,
    preferred_difficulty: Optional[int] = None,
    avoid_texts: Sequence[str] = (),
) -> List[GeneratedQuestionData]:
    """Writes, validates, reviews and de-duplicates new questions for one concept.

    Accepted questions are added to `duplicates` and carry their embedding in `q.embedding`.
    """
    plan = _difficulty_plan(count, preferred_difficulty)
    key_points = "\n".join(f"- {p}" for p in (concept.get("key_points") or [])) or "- (see source material)"
    avoid = "\n".join(f"- {t}" for t in list(avoid_texts)[-12:]) or "- (none yet)"
    prompt = QUESTION_PROMPT.format(
        concept=concept.get("concept", "Concept"),
        topic=concept.get("topic", "General"),
        summary=concept.get("summary") or "",
        key_points=key_points,
        source=source[:7000],
        count=count,
        difficulties=", ".join(str(d) for d in plan),
        avoid=avoid,
        types=QUESTION_TYPES_FOR_PROMPT,
    )
    data = await _call(
        prompt,
        "You are an expert teacher and assessment designer. Respond only with valid JSON.",
        0.4,
    )
    excerpt = "; ".join(concept.get("key_points") or []) or source
    built = [build_question(item, concept, excerpt) for item in _items(data, "questions")]
    candidates = [q for q in built if q is not None]
    if not candidates:
        return []

    candidates = await review_questions(candidates, source)
    if not candidates:
        return []

    excluded = set(excluded_fingerprints or [])
    vectors = await embed_texts([question_signature(q.question_text, _answer_text(q)) for q in candidates])
    accepted: List[GeneratedQuestionData] = []
    for q, vec in zip(candidates, vectors):
        signature = question_signature(q.question_text, _answer_text(q))
        if q.fingerprint in excluded or duplicates.is_duplicate(signature, vec):
            continue
        duplicates.add(signature, vec)
        q.embedding = vec
        q.concept_id = concept.get("id")
        accepted.append(q)
    return accepted


def _answer_text(q: GeneratedQuestionData) -> str:
    return next((o["text"] for o in q.options if o["key"] == q.correct_option), "")


def _row_signature(row: Dict[str, Any]) -> str:
    options = row.get("options") or []
    answer = next((o.get("text", "") for o in options if isinstance(o, dict) and o.get("key") == row.get("correct_option")), "")
    return question_signature(row.get("question_text", ""), answer)


def row_to_question(row: Dict[str, Any]) -> GeneratedQuestionData:
    citation = row.get("citation_metadata") or {}
    q = GeneratedQuestionData(
        topic=row.get("topic") or "General",
        concept=row.get("concept") or "Concept",
        difficulty=int(row.get("difficulty") or 2),
        question_text=row.get("question_text", ""),
        options=row.get("options") or [],
        correct_option=row.get("correct_option", "A"),
        explanation=row.get("explanation", ""),
        question_type=row.get("question_type") or "conceptual",
        document_id=row.get("document_id"),
        document_name=citation.get("document_name"),
        page_number=row.get("page_number") or citation.get("page_number") or 1,
        source_excerpt=row.get("source_excerpt"),
        quality_score=float(row.get("quality_score") or 1.0),
        fingerprint=row.get("fingerprint"),
    )
    q.embedding = row.get("embedding")
    q.concept_id = row.get("concept_id")
    return q


async def store_questions(workspace_id: str, questions: Iterable[GeneratedQuestionData]) -> int:
    stored = 0
    for q in questions:
        saved = await quiz_repo.add_to_question_bank(
            workspace_id=workspace_id,
            topic=q.topic,
            concept=q.concept,
            difficulty=q.difficulty,
            question_text=q.question_text,
            options=q.options,
            correct_option=q.correct_option,
            explanation=q.explanation,
            document_id=q.document_id,
            page_number=q.page_number,
            source_excerpt=q.source_excerpt,
            citation_metadata={"document_name": q.document_name, "page_number": q.page_number},
            generation_metadata={"generator": GENERATOR_TAG, "model": settings.gemini_generation_model},
            fingerprint=q.fingerprint,
            question_type=q.question_type,
            quality_score=q.quality_score,
            concept_id=getattr(q, "concept_id", None),
            embedding=getattr(q, "embedding", None),
            generator=GENERATOR_TAG,
        )
        if saved:
            stored += 1
    return stored


def _target_rank(targets: Sequence[Any]) -> Dict[str, float]:
    """Weight of each targeted concept name: earlier targets (bigger gaps) weigh more."""
    names: List[str] = []
    for t in targets or []:
        name = t.get("concept") if isinstance(t, dict) else t
        if name and normalize_concept_name(str(name)) not in names:
            names.append(normalize_concept_name(str(name)))
    n = len(names)
    return {name: 3.0 * (1 - i / (n + 1)) for i, name in enumerate(names)}


def select_questions(
    rows: List[Dict[str, Any]],
    count: int,
    targets: Sequence[Any] = (),
    preferred_difficulty: int = 2,
    excluded_fingerprints: Optional[Set[str]] = None,
    excluded_texts: Sequence[str] = (),
    seed: Optional[int] = None,
) -> List[GeneratedQuestionData]:
    """Picks a varied set of unseen bank questions for the targeted concepts and difficulty.

    Questions already served (by fingerprint) are skipped, and so is anything that repeats them in
    other words. At most one question per concept is used until every concept has one.
    """
    excluded_fps = set(excluded_fingerprints or [])
    seen = DuplicateIndex()
    for text in excluded_texts or []:
        seen.add(text)
    available = []
    for row in rows:
        if row.get("fingerprint") in excluded_fps:
            seen.add(_row_signature(row), row.get("embedding"))
        else:
            available.append(row)
    if not available:
        return []

    weights = _target_rank(targets)
    rng = random.Random(seed)

    def concept_key(row):
        return normalize_concept_name(row.get("concept") or "")

    def score(row) -> float:
        name = concept_key(row)
        target = weights.get(name, 0.0)
        if not target and weights:
            target = max((w * 0.8 for t, w in weights.items() if lexical_similarity(t, name) >= 0.6), default=0.0)
        diff = 2.0 - abs(int(row.get("difficulty") or 2) - preferred_difficulty)
        return target + diff + 0.5 * float(row.get("quality_score") or 1.0) + rng.random() * 0.75

    ranked = sorted(available, key=score, reverse=True)
    distinct = len({concept_key(r) for r in ranked})
    cap = 1 if distinct >= count else math.ceil(count / max(1, distinct))

    picked: List[Dict[str, Any]] = []
    per_concept: Counter = Counter()
    for limit in (cap, count):
        for row in ranked:
            if len(picked) >= count:
                break
            if row in picked or per_concept[concept_key(row)] >= limit:
                continue
            signature = _row_signature(row)
            if seen.is_duplicate(signature, row.get("embedding")):
                continue
            seen.add(signature, row.get("embedding"))
            picked.append(row)
            per_concept[concept_key(row)] += 1
    return [row_to_question(r) for r in picked]


class QuestionBankService:
    async def fill(self, workspace_id: str, chunks: List[Dict[str, Any]], served_fingerprints: Set[str], on_progress=None) -> int:
        """Tops up every concept that has fewer than REFILL_BELOW unserved questions."""
        concepts = await concept_map_service.get_workspace_concepts(workspace_id)
        if not concepts:
            return 0
        rows = await quiz_repo.list_question_bank(workspace_id, limit=100000)
        duplicates = DuplicateIndex()
        for row in rows:
            duplicates.add(_row_signature(row), row.get("embedding"))

        def rows_for(concept):
            return [
                r for r in rows
                if (r.get("concept_id") and r.get("concept_id") == concept.get("id"))
                or normalize_concept_name(r.get("concept") or "") == normalize_concept_name(concept["concept"])
            ]

        todo = []
        for c in concepts:
            own = rows_for(c)
            unserved = [r for r in own if r.get("fingerprint") not in served_fingerprints]
            if len(unserved) < REFILL_BELOW and len(own) < MAX_PER_CONCEPT:
                todo.append((c, [r.get("question_text", "") for r in own]))

        # Interleave documents so every document gets questions early
        by_doc: Dict[str, List] = {}
        for item in todo:
            by_doc.setdefault(str(item[0].get("document_id")), []).append(item)
        ordered = []
        while any(by_doc.values()):
            for key in list(by_doc):
                if by_doc[key]:
                    ordered.append(by_doc[key].pop(0))

        semaphore = asyncio.Semaphore(BUILD_CONCURRENCY)
        added = 0
        done = 0

        async def run(concept, existing_texts):
            nonlocal added, done
            async with semaphore:
                source = concept_map_service.source_text(concept, chunks)
                for attempt in range(GENERATION_ATTEMPTS):
                    try:
                        questions = await asyncio.wait_for(
                            generate_for_concept(
                                concept, source, TARGET_PER_CONCEPT, duplicates,
                                excluded_fingerprints=served_fingerprints, avoid_texts=existing_texts,
                            ),
                            timeout=GENERATION_TIMEOUT_SECONDS * 2,
                        )
                        added += await store_questions(workspace_id, questions)
                        break
                    except Exception as e:
                        # Long enough for a rate-limited or overloaded provider to recover
                        # (waits of 30, 60, 90 and 120 s: about five minutes in all)
                        wait = 30 * (attempt + 1)
                        last = attempt == GENERATION_ATTEMPTS - 1
                        logger.warning(
                            f"Question generation for '{concept['concept']}' failed: {type(e).__name__}: {e}" if last else
                            f"Question generation for '{concept['concept']}' failed ({type(e).__name__}: {e}); "
                            f"retrying in {wait}s."
                        )
                        if not last:
                            await asyncio.sleep(wait)
                done += 1
                if on_progress:
                    on_progress(done, len(ordered), added)

        await asyncio.gather(*(run(c, texts) for c, texts in ordered))
        return added

    async def candidates(
        self,
        workspace_id: str,
        count: int,
        targets: Sequence[Any],
        preferred_difficulty: int,
        excluded_fingerprints: Set[str],
        excluded_texts: Sequence[str],
    ) -> List[GeneratedQuestionData]:
        rows = await quiz_repo.list_question_bank(workspace_id, limit=100000)
        return select_questions(
            rows, count, targets, preferred_difficulty, excluded_fingerprints, excluded_texts
        )


question_bank_service = QuestionBankService()
