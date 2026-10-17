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
# Front text used by the earlier generator, which copied raw PDF text onto the back of cards
_LEGACY_FRONT_PREFIX = "What is the key mechanism of "
# "<Subject> is/are/refers to ..." definitional sentences
_DEFINITION = re.compile(r"^([A-Z][\w\-/()]*(?:\s+[\w\-/()]+){0,6}?)\s+(is|are|refers to|means)\s+", re.UNICODE)


class SecondaryService:
    async def get_or_generate_flashcards(self, workspace_id: str) -> List[Dict[str, Any]]:
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

    @staticmethod
    def _task_id(workspace_id: str, kind: str, concept: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (concept or "concept").lower()).strip("-")[:60] or "concept"
        return f"task_{workspace_id}_{kind}_{slug}"

    async def _build_tasks(self, workspace_id: str, ws_name: str, user_id: str) -> List[Dict[str, Any]]:
        """Builds the current task list from the learner's BKT knowledge gaps and concept mastery."""
        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id=user_id)
        all_mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id=user_id)

        tasks: List[Dict[str, Any]] = []
        covered = set()

        # Priority 1: active knowledge gaps (critical first), the top two scheduled for today
        for g in gaps:
            if g.get("gap_status") in ("strong", "resolved"):
                continue
            c_name = g.get("concept", "Concept")
            t_name = g.get("topic", "Topic")
            gap_p = float(g.get("gap_priority", 0.5) or 0.5)
            tasks.append({
                "id": self._task_id(workspace_id, "review", c_name),
                "title": f"Review & Remediate: {c_name}",
                "description": f"Targeted review to address an active knowledge gap in {t_name}. Priority: {round(gap_p * 100)}%.",
                "estimatedMinutes": 25,
                "scheduledFor": "today" if len(tasks) < 2 else "this_week",
                "completed": False,
                "tag": c_name,
                "priority": "high" if gap_p >= 0.6 else "medium",
            })
            covered.add(c_name.lower())

        # Priority 2: developing concepts (50-80% mastery) that are not already a gap task
        for m in sorted(all_mastery, key=lambda x: x.get("p_mastery", 0.5)):
            c_name = m.get("concept", "Concept")
            p_m = float(m.get("p_mastery", 0.5) or 0.5)
            if 0.5 <= p_m < 0.8 and c_name.lower() not in covered:
                tasks.append({
                    "id": self._task_id(workspace_id, "practice", c_name),
                    "title": f"Practice Problems: {c_name}",
                    "description": f"Strengthen concept retention through practice. Current mastery: {round(p_m * 100)}%.",
                    "estimatedMinutes": 30,
                    "scheduledFor": "this_week" if len(tasks) < 4 else "upcoming",
                    "completed": False,
                    "tag": c_name,
                    "priority": "medium",
                })
                covered.add(c_name.lower())

        # Starter tasks until the learner has quiz evidence
        if not tasks:
            tasks = [
                {
                    "id": self._task_id(workspace_id, "starter", "diagnostic"),
                    "title": f"Initial Syllabus Diagnostic in {ws_name}",
                    "description": "Complete diagnostic assessment to establish baseline concept mastery.",
                    "estimatedMinutes": 20,
                    "scheduledFor": "today",
                    "completed": False,
                    "tag": "Diagnostic",
                    "priority": "high",
                },
                {
                    "id": self._task_id(workspace_id, "starter", "core-concepts"),
                    "title": f"Read Core Concepts in {ws_name}",
                    "description": "Review indexed source documents and discuss key definitions with AI Tutor.",
                    "estimatedMinutes": 35,
                    "scheduledFor": "this_week",
                    "completed": False,
                    "tag": "Fundamentals",
                    "priority": "medium",
                },
            ]
        return tasks

    async def get_or_generate_study_plan(
        self,
        workspace_id: str,
        user_id: str = "default_user",
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Returns the workspace's adaptive study plan. Tasks are rebuilt from the latest knowledge gaps
        and mastery on every call, so the plan follows quiz results. Tasks the learner already ticked
        off are kept (and stay completed); open tasks that no longer apply are dropped.

        If the workspace's target completion date is before `today`, no plan is generated: the
        result has no tasks and target_passed=True, so the learner is asked to set a new date.
        """
        today = today or client_today()
        ws = await workspace_repo.get_by_id(workspace_id)
        ws_name = ws.get("name", "Workspace") if ws else "Workspace"
        daily = (ws.get("daily_target_minutes") or 45) if ws else 45
        target = parse_date(ws.get("target_date")) if ws else None
        timing = {
            "target_date": target.isoformat() if target else None,
            "days_remaining": (target - today).days if target else None,
            "target_passed": bool(target and target < today),
        }

        existing = await study_plan_repo.get_by_workspace(workspace_id)
        if timing["target_passed"]:
            return {
                "workspace_id": workspace_id,
                "daily_target_minutes": daily,
                "today_completed_minutes": 0,
                "weekly_target_minutes": daily * 5,
                "week_completed_minutes": 0,
                "tasks": [],
                **timing,
            }
        plan = await self._build_plan(workspace_id, ws_name, user_id, daily, existing)
        return {**plan, **timing}

    async def _build_plan(
        self,
        workspace_id: str,
        ws_name: str,
        user_id: str,
        daily: int,
        existing: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        old_tasks = (existing or {}).get("tasks") or []
        fresh = await self._build_tasks(workspace_id, ws_name, user_id)

        completed_ids = {t["id"] for t in old_tasks if t.get("completed")}
        fresh_ids = {t["id"] for t in fresh}
        tasks = [t for t in old_tasks if t.get("completed") and t["id"] not in fresh_ids]
        for t in fresh:
            t["completed"] = t["id"] in completed_ids
            tasks.append(t)

        if existing and [(t["id"], t.get("completed")) for t in old_tasks] == [(t["id"], t["completed"]) for t in tasks]:
            return existing

        plan_data = {
            "workspace_id": workspace_id,
            "daily_target_minutes": daily,
            "today_completed_minutes": (existing or {}).get("today_completed_minutes", 0),
            "weekly_target_minutes": daily * 5,
            "week_completed_minutes": (existing or {}).get("week_completed_minutes", 0),
            "tasks": tasks,
        }
        saved_plan = await study_plan_repo.save_plan(plan_data)
        await activity_repo.add_activity(
            workspace_id=workspace_id,
            event_type="study_plan_generated",
            title="Study Plan Updated" if existing else "Personalized Study Plan Generated",
            description=f"{len([t for t in tasks if not t['completed']])} open tasks tailored to current mastery gaps.",
        )
        return saved_plan

secondary_service = SecondaryService()
