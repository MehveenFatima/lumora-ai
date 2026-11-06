import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timezone
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.secondary import flashcard_repo, study_plan_repo, activity_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.services.knowledge_gap_engine import knowledge_gap_engine
from backend.app.core.dates import client_today, parse_date
from backend.app.core.logging import get_logger
from backend.app.services.text_cleanup import clean_label, clean_study_text, split_sentences, truncate_at_sentence

logger = get_logger(__name__)

FLASHCARD_TARGET = 10
FLASHCARD_SOURCE_LIMIT = 12
FLASHCARD_AI_BUDGET_SECONDS = 20
# Time allowed to write a concept-based deck while the learner waits
FLASHCARD_DECK_BUDGET_SECONDS = 40
# Front text used by the earlier generator, which copied raw PDF text onto the back of cards
_LEGACY_FRONT_PREFIX = "What is the key mechanism of "
# "<Subject> is/are/refers to ..." definitional sentences
_DEFINITION = re.compile(r"^([A-Z][\w\-/()]*(?:\s+[\w\-/()]+){0,6}?)\s+(is|are|refers to|means)\s+", re.UNICODE)


class SecondaryService:
    async def get_or_generate_flashcards(self, workspace_id: str) -> List[Dict[str, Any]]:
        from backend.app.services.study_prep import ai_available

        if ai_available():
            return await self._concept_flashcards(workspace_id)
        return await self._offline_flashcards(workspace_id)

    async def _concept_flashcards(self, workspace_id: str) -> List[Dict[str, Any]]:
        """The concept-based deck. While it is being written, any older deck is shown instead."""
        from backend.app.services import flashcard_builder
        from backend.app.services.concept_map import concept_map_service
        from backend.app.services.study_prep import study_prep_service, workspace_chunks

        existing = await flashcard_repo.list_by_workspace(workspace_id)
        if any(c.get("generator") == flashcard_builder.GENERATOR_TAG for c in existing):
            return existing
        if not study_prep_service.is_running(workspace_id):
            concepts = await concept_map_service.get_workspace_concepts(workspace_id)
            if concepts:
                chunks = await workspace_chunks(workspace_id)
                added = await study_prep_service.prepare_flashcards(
                    workspace_id, concepts, chunks, budget_seconds=FLASHCARD_DECK_BUDGET_SECONDS
                )
                if added:
                    return await flashcard_repo.list_by_workspace(workspace_id)
            study_prep_service.schedule(workspace_id, force=True)
        return existing

    async def _offline_flashcards(self, workspace_id: str) -> List[Dict[str, Any]]:
        existing = await flashcard_repo.list_by_workspace(workspace_id)
        if existing and any(str(c.get("front", "")).startswith(_LEGACY_FRONT_PREFIX) for c in existing):
            # Decks from the earlier generator copied raw PDF text onto the cards; rebuild them
            await flashcard_repo.delete_by_workspace(workspace_id)
            existing = []
        if existing and len(existing) >= 6:
            return existing

        docs = await document_repo.list_by_workspace(workspace_id)
        if not docs:
            return []

        all_chunks = []
        for d in docs:
            chunks = await chunk_repo.get_chunks_by_document(workspace_id, str(d["id"]))
            all_chunks.extend(chunks)
        if not all_chunks:
            return []

        sources = self._flashcard_sources(all_chunks)
        if not sources:
            return []

        generated_cards = await self._ai_flashcards(sources)
        if len(generated_cards) < 6:
            seen = {c["front"].lower() for c in generated_cards}
            for card in self._extractive_flashcards(sources):
                if card["front"].lower() not in seen:
                    generated_cards.append(card)
                    seen.add(card["front"].lower())
                if len(generated_cards) >= FLASHCARD_TARGET:
                    break

        generated_cards = generated_cards[:FLASHCARD_TARGET]
        if not generated_cards:
            return []

        saved = await flashcard_repo.save_flashcards(workspace_id, generated_cards)
        await activity_repo.add_activity(
            workspace_id=workspace_id,
            event_type="flashcards_generated",
            title="Flashcards Generated",
            description=f"Generated {len(saved)} spaced-repetition flashcards from workspace resources.",
        )
        return saved

    @staticmethod
    def _flashcard_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cleaned, evenly spread source passages with their concept and citation."""
        usable = []
        for c in chunks:
            heading = c.get("heading")
            text = clean_study_text(c.get("text") or c.get("content") or "", heading)
            if len(text) < 60:
                continue
            usable.append({
                "text": text,
                "concept": clean_label(heading) or "Core Concepts",
                "document": c.get("document_name") or "Workspace Notes",
                "page": c.get("page_number") or 1,
            })
        if len(usable) > FLASHCARD_SOURCE_LIMIT:
            step = len(usable) / FLASHCARD_SOURCE_LIMIT
            usable = [usable[int(i * step)] for i in range(FLASHCARD_SOURCE_LIMIT)]
        return usable

    async def _ai_flashcards(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Asks the AI provider for question/answer cards grounded in the source passages."""
        try:
            from backend.app.ai.gateway import ai_gateway
            from backend.app.ai.types import AIRequest, TaskType

            passages = "\n\n".join(
                f"[{i}] (concept: {s['concept']})\n{truncate_at_sentence(s['text'], 900)}" for i, s in enumerate(sources)
            )
            request = AIRequest(
                prompt=(
                    f"Create {FLASHCARD_TARGET} study flashcards from the numbered passages below.\n"
                    "Rules:\n"
                    "- front: one clear question a student should be able to answer, ending with '?'.\n"
                    "- back: the answer in 1-2 complete sentences, at most 220 characters.\n"
                    "- concept: a short topic name (2-5 words).\n"
                    "- source: the number of the passage the card is based on.\n"
                    "- Use only facts stated in the passages. Never mention question numbers, card numbers, "
                    "file names, page numbers or the passages themselves.\n"
                    "- Cover different ideas; no two cards may ask the same thing.\n\n"
                    f"PASSAGES:\n{passages}\n\n"
                    'Return JSON: {"cards": [{"front": "...", "back": "...", "concept": "...", "source": 0}]}'
                ),
                system_prompt="You write concise, accurate study flashcards. Respond only with valid JSON.",
                task_type=TaskType.FLASHCARDS,
                temperature=0.2,
            )
            response = await asyncio.wait_for(ai_gateway.generate_structured(request), timeout=FLASHCARD_AI_BUDGET_SECONDS)
        except Exception as e:
            logger.info(f"AI flashcard generation unavailable, using extractive cards: {e}")
            return []

        data = getattr(response, "structured_data", None) if response else None
        items = data.get("cards", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        cards: List[Dict[str, Any]] = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            front = clean_study_text(str(item.get("front", "")))
            back = truncate_at_sentence(clean_study_text(str(item.get("back", ""))), 260)
            if len(front) < 10 or len(back) < 15 or not front.endswith("?") or front.lower() in seen:
                continue
            try:
                src = sources[int(item.get("source", 0))]
            except (ValueError, TypeError, IndexError):
                src = sources[0]
            seen.add(front.lower())
            cards.append({
                "front": front,
                "back": back,
                "concept": clean_label(str(item.get("concept") or "")) or src["concept"],
                "source_document": src["document"],
                "source_page": src["page"],
                "interval_days": 1,
            })
        return cards

    @staticmethod
    def _extractive_flashcards(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Offline fallback: turns definitional sentences into question/answer cards."""
        cards: List[Dict[str, Any]] = []
        for s in sources:
            sentences = [x for x in split_sentences(s["text"]) if 40 <= len(x) <= 400]
            if not sentences:
                continue
            front, back = None, None
            for sentence in sentences:
                m = _DEFINITION.match(sentence)
                if m and len(m.group(1).split()) <= 5:
                    subject, verb = m.group(1).strip(), m.group(2).lower()
                    front = f"What {'are' if verb == 'are' else 'is'} {subject}?"
                    back = sentence
                    break
            if not front:
                front = f"What is the key idea behind {s['concept']}?"
                back = " ".join(sentences[:2])
            cards.append({
                "front": front,
                "back": truncate_at_sentence(back, 260),
                "concept": s["concept"],
                "source_document": s["document"],
                "source_page": s["page"],
                "interval_days": 1,
            })
        return cards

    async def get_or_generate_study_plan(self, workspace_id: str, today: Optional[date] = None) -> Dict[str, Any]:
        """Kept for older callers: the day-by-day plan now lives in study_plan_service."""
        from backend.app.services.study_plan_service import study_plan_service

        return await study_plan_service.get_plan(workspace_id, today=today)


secondary_service = SecondaryService()
