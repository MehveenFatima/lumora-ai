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

    async def get_or_generate_study_plan(
        self,
        workspace_id: str,
        user_id: str = "presentation-demo-user",
    ) -> Dict[str, Any]:
        existing = await study_plan_repo.get_by_workspace(workspace_id)
        if existing and existing.get("tasks"):
            return existing

        ws = await workspace_repo.get_by_id(workspace_id)
        ws_name = ws.get("name", "Workspace") if ws else "Workspace"

        # Query learner knowledge gaps and BKT mastery to tailor tasks
        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id=user_id)
        all_mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id=user_id)

        tasks = []
        task_idx = 1

        # Priority 1: High severity knowledge gaps (Scheduled for Today)
        for g in gaps:
            c_name = g.get("concept", "Concept")
            t_name = g.get("topic", "Topic")
            gap_p = float(g.get("gap_priority", 0.5))
            tasks.append({
                "id": f"task_{workspace_id}_{task_idx}",
                "title": f"Review & Remediate: {c_name}",
                "description": f"Targeted review to address active knowledge gap in {t_name}. Priority: {round(gap_p * 100)}%.",
                "estimatedMinutes": 25,
                "scheduledFor": "today" if len(tasks) < 2 else "this_week",
                "completed": False,
                "tag": c_name,
                "priority": "high" if gap_p >= 0.6 else "medium",
            })
            task_idx += 1

        # Priority 2: Developing concepts from mastery
        for m in all_mastery:
            c_name = m.get("concept", "Concept")
            p_m = m.get("p_mastery", 0.5)
            if 0.5 <= p_m < 0.8 and not any(t["tag"] == c_name for t in tasks):
                tasks.append({
                    "id": f"task_{workspace_id}_{task_idx}",
                    "title": f"Practice Problems: {c_name}",
                    "description": f"Strengthen concept retention through practice. Current mastery: {round(p_m * 100)}%.",
                    "estimatedMinutes": 30,
                    "scheduledFor": "this_week" if len(tasks) < 4 else "upcoming",
                    "completed": False,
                    "tag": c_name,
                    "priority": "medium",
                })
                task_idx += 1

        # Fallback default tasks if empty
        if not tasks:
            tasks = [
                {
                    "id": f"task_{workspace_id}_1",
                    "title": f"Initial Syllabus Diagnostic in {ws_name}",
                    "description": "Complete diagnostic assessment to establish baseline concept mastery.",
                    "estimatedMinutes": 20,
                    "scheduledFor": "today",
                    "completed": False,
                    "tag": "Diagnostic",
                    "priority": "high",
                },
                {
                    "id": f"task_{workspace_id}_2",
                    "title": f"Read Core Concepts in {ws_name}",
                    "description": "Review indexed source documents and discuss key definitions with AI Tutor.",
                    "estimatedMinutes": 35,
                    "scheduledFor": "this_week",
                    "completed": False,
                    "tag": "Fundamentals",
                    "priority": "medium",
                },
            ]

        plan_data = {
            "workspace_id": workspace_id,
            "daily_target_minutes": ws.get("daily_target_minutes", 45) if ws else 45,
            "today_completed_minutes": 0,
            "weekly_target_minutes": (ws.get("daily_target_minutes", 45) if ws else 45) * 5,
            "week_completed_minutes": 0,
            "tasks": tasks,
        }

        saved_plan = await study_plan_repo.save_plan(plan_data)
        await activity_repo.add_activity(
            workspace_id=workspace_id,
            event_type="study_plan_generated",
            title="Personalized Study Plan Generated",
            description=f"Constructed {len(tasks)} personalized learning milestones tailored to current mastery gaps.",
        )
        return saved_plan


secondary_service = SecondaryService()
