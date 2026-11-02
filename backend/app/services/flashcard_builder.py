"""
Flashcards written per concept of the topic map.

Each concept gets a few cards that each test a different fact or skill (definition, formula, rule,
comparison, typical mistake, small worked example), so the deck covers the whole document instead
of rephrasing one sentence. New cards are checked against the whole deck by meaning, so a card
that repeats an existing one in other words is dropped.
"""
import asyncio
import re
from typing import Any, Dict, List, Optional, Sequence

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.services.concept_map import concept_map_service, normalize_concept_name
from backend.app.services.similarity import DuplicateIndex, embed_texts
from backend.app.services.text_cleanup import truncate_at_sentence

logger = get_logger(__name__)

GENERATOR_TAG = "concept_v2"
CONCEPTS_PER_REQUEST = 5
REQUEST_CONCURRENCY = 2
REQUEST_TIMEOUT_SECONDS = 90
# Meaning-based threshold for two cards testing the same fact
CARD_SEMANTIC_DUPLICATE = 0.88

FLASHCARD_PROMPT = """Write study flashcards for a student, the way the best spaced-repetition deck for these notes would be written.

{concepts}

For each concept above write {per_concept} flashcards.

Rules:
- Each card tests one specific fact or skill, and every card tests a different one: a definition, a
  formula and when it applies, a condition or rule, a property, a step of a method, how it differs from
  a close idea, a typical mistake, or a small worked example (front: a short problem with numbers,
  back: the answer and the key step).
- Never write two cards about the same fact, even in different words. If two fronts would have the
  same answer, keep only one of them.
- front: a precise, self-contained question or prompt ending with "?" or ":". Never refer to "this",
  "the above", the slide, the lesson or the notes.
- back: the answer in 1-2 sentences, or a formula with a short note; at most 240 characters.
- For mathematics and science, include the formulas and at least one small worked-example card per
  concept whenever the material has calculations. Write maths in plain text (sqrt(x), x^2, |z|).
- Use only facts from the material. Ignore lesson instructions and activities ("Independent
  Practice", "Try these", "Exit ticket").
{avoid}
Return JSON: {{"cards": [{{"concept_index": 0, "front": "...", "back": "...", "source_page": 1}}]}}
"""


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _concept_block(index: int, concept: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
    points = "\n".join(f"  - {p}" for p in concept.get("key_points") or [])
    source = concept_map_service.source_text(concept, chunks, limit=2500)
    return (
        f"CONCEPT [{index}]: {concept['concept']} (topic: {concept.get('topic') or 'General'})\n"
        f"Summary: {concept.get('summary') or ''}\n"
        f"Key points:\n{points or '  - (see material)'}\n"
        f"Material:\n{source}\n"
    )


class CardDeduplicator:
    """Rejects cards that repeat a card already in the deck, by meaning or by wording."""

    def __init__(self, cards: Sequence[Dict[str, Any]] = ()):
        self.meaning = DuplicateIndex(semantic_threshold=CARD_SEMANTIC_DUPLICATE, lexical_threshold=0.6)
        self.fronts = DuplicateIndex(lexical_threshold=0.75)
        # Two cards with the same answer test the same fact, however differently the fronts are worded
        self.backs = DuplicateIndex(lexical_threshold=0.7)
        for c in cards:
            self.add(c, c.get("embedding"))

    @staticmethod
    def signature(card: Dict[str, Any]) -> str:
        return f"{card.get('front', '')} {card.get('back', '')}"

    def add(self, card: Dict[str, Any], vector=None) -> None:
        self.meaning.add(self.signature(card), vector)
        self.fronts.add(card.get("front", ""))
        self.backs.add(card.get("back", ""))

    def is_duplicate(self, card: Dict[str, Any], vector=None) -> bool:
        # Same answer in other words, or the same question asked again
        if self.meaning.is_duplicate(self.signature(card), vector):
            return True
        return self.fronts.is_duplicate(card.get("front", "")) or self.backs.is_duplicate(card.get("back", ""))


async def _request(concepts: List[Dict[str, Any]], chunks: List[Dict[str, Any]], per_concept: str, avoid: List[str]) -> List[Dict[str, Any]]:
    from backend.app.ai.gateway import ai_gateway
    from backend.app.ai.types import AIRequest, TaskType

    blocks = "\n".join(_concept_block(i, c, chunks) for i, c in enumerate(concepts))
    avoid_text = ""
    if avoid:
        avoid_text = "- The deck already has these cards; do not repeat or rephrase them:\n" + "\n".join(
            f"  * {a}" for a in avoid[-40:]
        ) + "\n"
    request = AIRequest(
        prompt=FLASHCARD_PROMPT.format(concepts=blocks, per_concept=per_concept, avoid=avoid_text),
        system_prompt="You are an expert teacher who writes precise, varied flashcards. Respond only with valid JSON.",
        task_type=TaskType.FLASHCARDS,
        temperature=0.3,
        model=settings.gemini_generation_model,
    )
    response = await asyncio.wait_for(ai_gateway.generate_structured(request), timeout=REQUEST_TIMEOUT_SECONDS)
    data = getattr(response, "structured_data", None)
    items = data.get("cards", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    cards = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            concept = concepts[int(item.get("concept_index", 0))]
        except (TypeError, ValueError, IndexError):
            continue
        front = _clean(item.get("front"))
        back = truncate_at_sentence(_clean(item.get("back")), 280)
        if len(front) < 8 or len(back) < 2 or not front.endswith(("?", ":")):
            continue
        if re.search(r"\b(this slide|the slide|the lesson|the notes|the above|the passage|the text)\b", front, re.IGNORECASE):
            continue
        pages = concept.get("source_pages") or []
        try:
            page = int(item.get("source_page") or (pages[0] if pages else 1))
        except (TypeError, ValueError):
            page = pages[0] if pages else 1
        cards.append({
            "front": front,
            "back": back,
            "concept": concept["concept"][:120],
            "source_document": concept.get("document_name") or "Workspace Notes",
            "source_page": page,
            "interval_days": 1,
            "document_id": str(concept["document_id"]) if concept.get("document_id") else None,
            "concept_id": concept.get("id"),
            "generator": GENERATOR_TAG,
        })
    return cards


async def write_cards(
    concepts: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    existing: Sequence[Dict[str, Any]] = (),
    per_concept: str = "2 or 3 (3 when the concept has several distinct facts)",
    budget_seconds: Optional[float] = None,
    max_per_concept: int = 4,
) -> List[Dict[str, Any]]:
    """New, de-duplicated cards for the given concepts (in concept order)."""
    if not concepts:
        return []
    dedup = CardDeduplicator(existing)
    avoid_by_concept: Dict[str, List[str]] = {}
    for c in existing:
        avoid_by_concept.setdefault(normalize_concept_name(c.get("concept", "")), []).append(c.get("front", ""))

    batches = [concepts[i:i + CONCEPTS_PER_REQUEST] for i in range(0, len(concepts), CONCEPTS_PER_REQUEST)]
    semaphore = asyncio.Semaphore(REQUEST_CONCURRENCY)

    async def run(batch):
        avoid = [f for c in batch for f in avoid_by_concept.get(normalize_concept_name(c["concept"]), [])]
        async with semaphore:
            try:
                return await _request(batch, chunks, per_concept, avoid)
            except Exception as e:
                logger.warning(f"Flashcard request failed ({type(e).__name__}: {e}).")
                return []

    jobs = [asyncio.create_task(run(b)) for b in batches]
    if budget_seconds:
        done, pending = await asyncio.wait(jobs, timeout=budget_seconds)
        for job in pending:
            job.cancel()
    else:
        await asyncio.gather(*jobs)
        done = set(jobs)

    raw: List[Dict[str, Any]] = []
    for job in jobs:
        if job in done and not job.cancelled() and job.exception() is None:
            raw.extend(job.result())
    if not raw:
        return []

    vectors = await embed_texts([CardDeduplicator.signature(c) for c in raw])
    new_per_concept: Dict[str, int] = {}
    accepted = []
    for card, vec in zip(raw, vectors):
        key = normalize_concept_name(card["concept"])
        if new_per_concept.get(key, 0) >= max_per_concept or dedup.is_duplicate(card, vec):
            continue
        dedup.add(card, vec)
        card["embedding"] = vec
        new_per_concept[key] = new_per_concept.get(key, 0) + 1
        accepted.append(card)
    return accepted


def least_covered(concepts: List[Dict[str, Any]], cards: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Concepts with the fewest cards first (ties: more key points first, then map order)."""
    counts: Dict[str, int] = {}
    for c in cards:
        key = normalize_concept_name(c.get("concept", ""))
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(
        enumerate(concepts),
        key=lambda ic: (counts.get(normalize_concept_name(ic[1]["concept"]), 0), -len(ic[1].get("key_points") or []), ic[0]),
    )
    return [c for _, c in ranked[:limit]]


def uncovered(concepts: List[Dict[str, Any]], cards: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    have = {normalize_concept_name(c.get("concept", "")) for c in cards}
    have_ids = {c.get("concept_id") for c in cards if c.get("concept_id")}
    return [c for c in concepts if c.get("id") not in have_ids and normalize_concept_name(c["concept"]) not in have]
