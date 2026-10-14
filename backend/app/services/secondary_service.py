import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.repositories.chunks import chunk_repo
from backend.app.repositories.documents import document_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.repositories.secondary import flashcard_repo, study_plan_repo, activity_repo
from backend.app.repositories.bkt import bkt_repo
from backend.app.services.knowledge_gap_engine import knowledge_gap_engine
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class SecondaryService:
    async def get_or_generate_flashcards(self, workspace_id: str) -> List[Dict[str, Any]]:
        existing = await flashcard_repo.list_by_workspace(workspace_id)
        if existing and len(existing) >= 6:
            return existing

        # Generate fresh flashcards from workspace chunks and documents
        docs = await document_repo.list_by_workspace(workspace_id)
        if not docs:
            return []

        all_chunks = []
        for d in docs:
            chunks = await chunk_repo.get_chunks_by_document(workspace_id, str(d["id"]))
            all_chunks.extend(chunks)

        if not all_chunks:
            return []

        generated_cards = []
        for c in all_chunks[:15]:
            text = c.get("text", "")
            heading = c.get("heading") or "Core Principle"
            doc_name = c.get("document_name") or "Workspace Notes"
            page = c.get("page_number", 1)

            # Heuristically extract question/answer definitions from sentences
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
            if not sentences:
                continue

            # First sentence as basis for front / back
            front_text = f"What is the key mechanism of {heading}?"
            back_text = sentences[0]
            if len(sentences) > 1:
                back_text += " " + sentences[1]

            generated_cards.append({
                "front": front_text,
                "back": back_text[:280],
                "concept": heading,
                "source_document": doc_name,
                "source_page": page,
                "interval_days": 1,
            })

            if len(generated_cards) >= 10:
                break

        if generated_cards:
            saved = await flashcard_repo.save_flashcards(workspace_id, generated_cards)
            await activity_repo.add_activity(
                workspace_id=workspace_id,
                event_type="flashcards_generated",
                title="Flashcards Generated",
                description=f"Generated {len(saved)} spaced-repetition flashcards from workspace resources.",
            )
            return saved

        return []

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
    ) -> Dict[str, Any]:
        """
        Returns the workspace's adaptive study plan. Tasks are rebuilt from the latest knowledge gaps
        and mastery on every call, so the plan follows quiz results. Tasks the learner already ticked
        off are kept (and stay completed); open tasks that no longer apply are dropped.
        """
        ws = await workspace_repo.get_by_id(workspace_id)
        ws_name = ws.get("name", "Workspace") if ws else "Workspace"
        daily = (ws.get("daily_target_minutes") or 45) if ws else 45

        existing = await study_plan_repo.get_by_workspace(workspace_id)
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
