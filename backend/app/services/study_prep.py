"""
Background preparation of a workspace's study material.

After a document is indexed (and whenever a quiz or the flashcards page finds work left to do),
one background job per workspace:
1. builds the topic map of every document that has none,
2. writes the flashcard deck (or adds cards for concepts of new documents),
3. fills the question bank, a few questions per concept at every difficulty.

The job is idempotent: each step only does what is missing, so it is safe to schedule repeatedly,
and an interrupted job (for example when a free-tier server sleeps) resumes on the next trigger.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.secondary import activity_repo, flashcard_repo
from backend.app.services import flashcard_builder
from backend.app.services.concept_map import concept_map_service
from backend.app.services.question_bank import question_bank_service

logger = get_logger(__name__)

# A finished job is not re-run sooner than this unless something changed (new document)
RERUN_AFTER_SECONDS = 120


def ai_available() -> bool:
    from backend.app.ai.gateway import ai_gateway
    from backend.app.ai.types import TaskType

    return ai_gateway.has_configured_provider(TaskType.QUIZ)


async def workspace_chunks(workspace_id: str) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for d in await document_repo.list_by_workspace(workspace_id):
        chunks.extend(await chunk_repo.get_chunks_by_document(workspace_id, str(d["id"])))
    return chunks


class StudyPreparationService:
    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._status: Dict[str, Dict[str, Any]] = {}

    def is_running(self, workspace_id: str) -> bool:
        task = self._tasks.get(workspace_id)
        return bool(task and not task.done())

    def status(self, workspace_id: str) -> Dict[str, Any]:
        state = dict(self._status.get(workspace_id) or {"state": "idle"})
        if self.is_running(workspace_id):
            state["state"] = "preparing"
        state.pop("finished_at", None)
        return state

    def schedule(self, workspace_id: str, force: bool = False) -> bool:
        """Starts the preparation job unless it is running (or finished moments ago). True if started."""
        if not ai_available() or self.is_running(workspace_id):
            return False
        last = self._status.get(workspace_id) or {}
        if not force and last.get("state") == "ready" and time.time() - last.get("finished_at", 0) < RERUN_AFTER_SECONDS:
            return False
        self._status[workspace_id] = {"state": "preparing", "stage": "topic_map"}
        self._tasks[workspace_id] = asyncio.create_task(self._run(workspace_id))
        return True

    def _set(self, workspace_id: str, **fields) -> None:
        self._status.setdefault(workspace_id, {}).update(fields)

    async def _run(self, workspace_id: str) -> None:
        try:
            from backend.app.repositories.workspaces import workspace_repo

            if await workspace_repo.is_sample(workspace_id):
                # Sample workspaces ship with their material; nothing to write
                self._set(workspace_id, state="ready", stage="done", finished_at=time.time())
                return
            concepts = await concept_map_service.ensure_workspace(workspace_id)
            self._set(workspace_id, concepts=len(concepts))
            if not concepts:
                self._set(workspace_id, state="ready", stage="done", finished_at=time.time())
                return
            chunks = await workspace_chunks(workspace_id)

            self._set(workspace_id, stage="flashcards")
            await self.prepare_flashcards(workspace_id, concepts, chunks)

            self._set(workspace_id, stage="questions")
            served = set(await bkt_repo.list_workspace_fingerprints(workspace_id))

            def progress(done: int, total: int, added: int) -> None:
                self._set(workspace_id, concepts_done=done, concepts_total=total, questions_added=added)

            added = await question_bank_service.fill(workspace_id, chunks, served, on_progress=progress)
            self._set(workspace_id, state="ready", stage="done", questions_added=added, finished_at=time.time())
            logger.info(f"Study material ready for workspace {workspace_id}: {len(concepts)} concepts, {added} new questions.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Study material preparation failed for workspace {workspace_id}: {e}", exc_info=True)
            self._set(workspace_id, state="failed", stage="done", finished_at=time.time())

    async def prepare_flashcards(
        self,
        workspace_id: str,
        concepts: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
        budget_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Writes the concept-based deck (retiring an older deck once the new one is saved), or adds
        cards for concepts that have none yet. Returns the cards added."""
        existing = await flashcard_repo.list_by_workspace(workspace_id)
        current = [c for c in existing if c.get("generator") == flashcard_builder.GENERATOR_TAG]
        if not current:
            cards = await flashcard_builder.write_cards(concepts, chunks, budget_seconds=budget_seconds)
            if len(cards) < min(6, len(concepts)):
                return []
            saved = await flashcard_repo.save_flashcards(workspace_id, cards)
            await flashcard_repo.delete_ids(workspace_id, [c["id"] for c in existing])
            await self._log(workspace_id, len(saved), rebuilt=bool(existing))
            return saved

        missing = flashcard_builder.uncovered(concepts, current)
        if not missing:
            return []
        cards = await flashcard_builder.write_cards(missing, chunks, existing=current, budget_seconds=budget_seconds)
        if not cards:
            return []
        saved = await flashcard_repo.save_flashcards(workspace_id, cards)
        await self._log(workspace_id, len(saved), rebuilt=False)
        return saved

    async def more_flashcards(self, workspace_id: str, budget_seconds: float = 40) -> List[Dict[str, Any]]:
        """Adds new cards for the least-covered concepts, never repeating the deck."""
        concepts = await concept_map_service.get_workspace_concepts(workspace_id)
        if not concepts:
            return []
        chunks = await workspace_chunks(workspace_id)
        existing = await flashcard_repo.list_by_workspace(workspace_id)
        current = [c for c in existing if c.get("generator") == flashcard_builder.GENERATOR_TAG]
        if not current:
            return await self.prepare_flashcards(workspace_id, concepts, chunks, budget_seconds=budget_seconds)
        targets = flashcard_builder.least_covered(concepts, current, limit=flashcard_builder.CONCEPTS_PER_REQUEST * 2)
        cards = await flashcard_builder.write_cards(
            targets, chunks, existing=current, per_concept="2", budget_seconds=budget_seconds, max_per_concept=2
        )
        if not cards:
            return []
        saved = await flashcard_repo.save_flashcards(workspace_id, cards)
        await self._log(workspace_id, len(saved), rebuilt=False)
        return saved

    @staticmethod
    async def _log(workspace_id: str, count: int, rebuilt: bool) -> None:
        try:
            await activity_repo.add_activity(
                workspace_id=workspace_id,
                event_type="flashcards_generated",
                title="Flashcards Rebuilt" if rebuilt else "Flashcards Generated",
                description=f"{'Rebuilt the deck with' if rebuilt else 'Added'} {count} flashcards covering the concepts in your notes.",
            )
        except Exception:
            pass


study_prep_service = StudyPreparationService()
