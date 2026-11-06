"""
Loads everything the day-by-day planner needs for a workspace, runs it, and stores the result.

See `study_planner` for the scheduling rules. This service adds:
- the inputs: topic map, BKT mastery and gaps, flashcard due dates, documents, settings;
- persistence: today's frozen task list, completions with their dates, auto-completions;
- ticking tasks off (today's, or a later one done ahead of time);
- the combined "today" view across all of a user's workspaces for the dashboard.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.dates import client_today, parse_date
from backend.app.core.logging import get_logger
from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.concepts import concept_repo
from backend.app.repositories.secondary import activity_repo, flashcard_repo, study_plan_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.services import study_planner as planner

logger = get_logger(__name__)

# Completions older than this are dropped from storage (they no longer affect any total)
KEEP_COMPLETIONS_DAYS = 400
DEFAULT_TZ_OFFSET = 330  # India Standard Time, used until the browser reports the real offset


class TaskNotFoundError(Exception):
    pass


class TaskLockedError(Exception):
    pass


class TargetPassedError(Exception):
    pass


def _dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class StudyPlanService:
    # ------------------------------------------------------------------ inputs

    async def _concept_states(self, workspace_id: str, user_id: str) -> List[planner.ConceptState]:
        topic_map = await concept_repo.list_by_workspace(workspace_id)
        if not topic_map:
            topic_map = await self._offline_topic_map(workspace_id)
        mastery = await bkt_repo.list_concept_mastery(workspace_id, user_id=user_id)
        gaps = await bkt_repo.list_knowledge_gaps(workspace_id, user_id=user_id)
        mastery_by = {str(m.get("concept", "")).strip().lower(): m for m in mastery if m.get("concept")}
        gaps_by = {str(g.get("concept", "")).strip().lower(): g for g in gaps if g.get("concept")}

        states: List[planner.ConceptState] = []
        seen = set()

        def add(concept: str, topic: str, position: int) -> None:
            key = concept.strip().lower()
            if not key or key in seen:
                return
            seen.add(key)
            m = mastery_by.get(key)
            g = gaps_by.get(key)
            evidence = None
            if m:
                evidence = _dt(m.get("last_attempt_at") or m.get("last_practiced_at") or m.get("updated_at"))
            if g and not evidence:
                evidence = _dt(g.get("updated_at"))
            p = None
            if m is not None:
                p = float(m.get("p_mastery") or 0.0)
            elif g is not None:
                p = 0.3  # a gap without a mastery row (older data): treat as weak
            states.append(planner.ConceptState(
                concept=concept.strip(),
                topic=(topic or (m or g or {}).get("topic") or "General").strip(),
                position=position,
                p_mastery=p,
                gap_status=(g or {}).get("gap_status"),
                gap_priority=float((g or {}).get("gap_priority") or 0.0),
                evidence_at=evidence,
            ))

        for i, c in enumerate(topic_map):
            add(str(c.get("concept") or ""), str(c.get("topic") or ""), i)
        # Concepts with quiz results that aren't in the topic map (older workspaces) still count
        offset = len(topic_map)
        for i, m in enumerate(list(mastery) + list(gaps)):
            add(str(m.get("concept") or ""), str(m.get("topic") or ""), offset + i)
        return states

    async def _offline_topic_map(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Without an AI provider the background job never builds a topic map, so the plan builds
        the heading-based one itself (fast, no AI). With AI, the background job builds it and the
        plan shows starter tasks until it's ready."""
        from backend.app.services.concept_map import concept_map_service

        if concept_map_service.ai_available():
            return []
        try:
            return await concept_map_service.ensure_workspace(workspace_id)
        except Exception as e:
            logger.warning(f"Could not build the heading-based topic map for {workspace_id}: {e}")
            return []

    async def _flashcards(self, workspace_id: str, today: date):
        cards = await flashcard_repo.list_by_workspace(workspace_id)
        due: Dict[date, int] = {}
        reviewed_today = 0
        for card in cards:
            d = parse_date(card.get("due_date"))
            key = today if d is None or d <= today else d
            due[key] = due.get(key, 0) + 1
            if parse_date(card.get("last_reviewed")) == today:
                reviewed_today += 1
        return due, reviewed_today

    async def _has_documents(self, workspace_id: str, ws: Dict[str, Any]) -> bool:
        if int(ws.get("document_count") or 0) > 0:
            return True
        from backend.app.repositories.documents import document_repo

        docs = await document_repo.list_by_workspace(workspace_id)
        return any(d.get("status") == "ready" for d in docs)

    # ------------------------------------------------------------------ core

    async def _run(
        self,
        workspace_id: str,
        today: date,
        tz_offset: int,
        user_id: str = "default_user",
        force_today: bool = False,
    ) -> Dict[str, Any]:
        ws = await workspace_repo.get_by_id(workspace_id) or {"id": workspace_id}
        daily = int(ws.get("daily_target_minutes") or 45)
        target = parse_date(ws.get("target_date"))
        timing = {
            "target_date": target.isoformat() if target else None,
            "days_remaining": (target - today).days if target else None,
            "target_passed": bool(target and target < today),
        }
        stored = await study_plan_repo.get_by_workspace(workspace_id) or {}
        completions: List[Dict[str, Any]] = list(stored.get("completions") or [])

        if timing["target_passed"]:
            return {
                "workspace": ws, "stored": stored, "timing": timing, "result": None,
                "completions": completions, "today": today,
            }

        concepts = await self._concept_states(workspace_id, user_id)
        flash_due, reviewed_today = await self._flashcards(workspace_id, today)

        snapshot = stored.get("snapshot")
        snapshot_date = parse_date(stored.get("snapshot_date"))
        same_day = snapshot is not None and snapshot_date == today
        previous = stored.get("previous_snapshot")
        if snapshot is not None and snapshot_date and snapshot_date < today:
            previous = snapshot
        keep_completed: List[Dict[str, Any]] = []
        if same_day:
            # Tasks for concepts that no longer exist (document deleted) drop out unless done today
            done_today = {str(c.get("task_id")) for c in completions if str(c.get("date")) == today.isoformat()}
            known = {c.key for c in concepts}
            snapshot = [
                t for t in snapshot
                if not t.get("concept") or str(t["concept"]).strip().lower() in known or t.get("id") in done_today
            ]
            if force_today:
                keep_completed = [t for t in snapshot if t.get("id") in done_today]

        inputs = planner.PlanInputs(
            today=today,
            target_date=target,
            daily_minutes=daily,
            concepts=concepts,
            has_documents=await self._has_documents(workspace_id, ws),
            flashcards_due=flash_due,
            flashcards_reviewed_today=reviewed_today,
            completions=completions,
            snapshot=None if (force_today or not same_day) else snapshot,
            snapshot_at=_dt(stored.get("snapshot_at")) if same_day else None,
            previous_snapshot=previous,
            workspace_id=workspace_id,
            tz_offset_minutes=tz_offset,
            now=datetime.now(timezone.utc),
            keep_today=keep_completed,
        )
        result = planner.build_plan(inputs)

        new_comps = result["new_completions"]
        all_comps = completions + new_comps
        changed = bool(new_comps) or result["snapshot_rebuilt"] or not stored
        if changed:
            cutoff = (today - timedelta(days=KEEP_COMPLETIONS_DAYS)).isoformat()
            all_comps = [c for c in all_comps if str(c.get("date", "")) >= cutoff]
            await study_plan_repo.save_plan({
                "workspace_id": workspace_id,
                "daily_target_minutes": result["daily_target_minutes"],
                "today_completed_minutes": result["today_completed_minutes"],
                "weekly_target_minutes": result["weekly_target_minutes"],
                "week_completed_minutes": result["week_completed_minutes"],
                "tasks": result["later_tasks"][:200],
                "completions": all_comps,
                "snapshot": result["snapshot"],
                "snapshot_date": today.isoformat(),
                "snapshot_at": (result["snapshot_at"] or datetime.now(timezone.utc)).isoformat(),
                "previous_snapshot": previous,
            })
        return {
            "workspace": ws, "stored": stored, "timing": timing, "result": result,
            "completions": all_comps, "today": today,
        }

    def _response(self, workspace_id: str, run: Dict[str, Any]) -> Dict[str, Any]:
        ws = run["workspace"]
        timing = run["timing"]
        result = run["result"]
        daily = int(ws.get("daily_target_minutes") or 45)
        if result is None:
            return {
                "workspace_id": workspace_id,
                "workspace_name": ws.get("name"),
                "daily_target_minutes": daily,
                "today_completed_minutes": 0,
                "weekly_target_minutes": daily * planner.WEEK_LENGTH,
                "week_completed_minutes": 0,
                "today_planned_minutes": 0,
                "needed_daily_minutes": daily,
                "on_track": True,
                "expected_finish_date": None,
                "coverage": {"total_concepts": 0, "mastered": 0, "in_progress": 0, "not_started": 0},
                "tasks": [],
                "date": run["today"].isoformat(),
                **timing,
            }
        return {
            "workspace_id": workspace_id,
            "workspace_name": ws.get("name"),
            "daily_target_minutes": result["daily_target_minutes"],
            "today_completed_minutes": result["today_completed_minutes"],
            "weekly_target_minutes": result["weekly_target_minutes"],
            "week_completed_minutes": result["week_completed_minutes"],
            "today_planned_minutes": result["today_planned_minutes"],
            "needed_daily_minutes": result["needed_daily_minutes"],
            "on_track": result["on_track"],
            "expected_finish_date": result["expected_finish_date"],
            "coverage": result["coverage"],
            "tasks": result["today_tasks"] + result["later_tasks"],
            "date": run["today"].isoformat(),
            **timing,
        }

    # ------------------------------------------------------------------ public

    async def get_plan(
        self, workspace_id: str, today: Optional[date] = None, tz_offset: int = DEFAULT_TZ_OFFSET,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        today = today or client_today()
        run = await self._run(workspace_id, today, tz_offset, user_id=user_id)
        return self._response(workspace_id, run)

    async def plan_more_today(
        self, workspace_id: str, today: Optional[date] = None, tz_offset: int = DEFAULT_TZ_OFFSET,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        """Rebuilds today's list from the latest results, keeping the tasks already done today."""
        today = today or client_today()
        run = await self._run(workspace_id, today, tz_offset, user_id=user_id, force_today=True)
        return self._response(workspace_id, run)

    async def toggle_task(
        self, workspace_id: str, task_id: str, today: Optional[date] = None, tz_offset: int = DEFAULT_TZ_OFFSET,
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        today = today or client_today()
        run = await self._run(workspace_id, today, tz_offset, user_id=user_id)
        if run["result"] is None:
            raise TargetPassedError()
        result = run["result"]
        task = planner.find_task(result, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        stored = await study_plan_repo.get_by_workspace(workspace_id) or {}
        completions = list(stored.get("completions") or [])
        snapshot = list(stored.get("snapshot") or result["snapshot"])
        today_iso = today.isoformat()

        if task.get("completed"):
            completions = [
                c for c in completions if not (c.get("task_id") == task_id and str(c.get("date")) == today_iso)
            ]
            # Don't tick it again automatically today after the learner unticked it
            for t in snapshot:
                if t.get("id") == task_id:
                    t["noAuto"] = True
        else:
            if task.get("scheduledDate") != today_iso:
                # Done ahead of time: it moves into today's list
                moved = {k: v for k, v in task.items() if k not in ("completed", "scheduledDate", "scheduledFor")}
                snapshot.append({**moved, "doneAhead": True})
            completions.append(planner.completion_record(task, today, datetime.now(timezone.utc)))
            try:
                await activity_repo.add_activity(
                    workspace_id=workspace_id,
                    event_type="study_task_completed",
                    title=f"Completed: {task.get('title')}",
                    description=f"{task.get('estimatedMinutes', 0)} minutes from today's study plan.",
                )
            except Exception as e:  # the tick itself must not fail because of the activity log
                logger.warning(f"Could not log study task completion: {e}")

        await study_plan_repo.save_plan({
            **stored,
            "workspace_id": workspace_id,
            "completions": completions,
            "snapshot": snapshot,
            "snapshot_date": today_iso,
            "snapshot_at": stored.get("snapshot_at") or datetime.now(timezone.utc).isoformat(),
        })
        return await self.get_plan(workspace_id, today=today, tz_offset=tz_offset, user_id=user_id)

    async def invalidate_today(self, workspace_id: str) -> None:
        """Called when the target date or daily minutes change: today's list is rebuilt next time
        (tasks already done today stay done)."""
        stored = await study_plan_repo.get_by_workspace(workspace_id)
        if not stored or stored.get("snapshot") is None:
            return
        await study_plan_repo.save_plan({**stored, "snapshot": None, "snapshot_date": None, "snapshot_at": None})

    async def today_overview(
        self, owner_id: str, today: Optional[date] = None, tz_offset: int = DEFAULT_TZ_OFFSET,
    ) -> Dict[str, Any]:
        """Today's tasks across every workspace the user owns, for the dashboard."""
        today = today or client_today()
        workspaces = await workspace_repo.list_by_owner(owner_id)
        tasks: List[Dict[str, Any]] = []
        summaries: List[Dict[str, Any]] = []
        for ws in workspaces:
            try:
                plan = await self.get_plan(ws["id"], today=today, tz_offset=tz_offset)
            except Exception as e:
                logger.warning(f"Could not build the study plan for workspace {ws.get('id')}: {e}")
                continue
            todays = [t for t in plan["tasks"] if t.get("scheduledDate") == today.isoformat()]
            for t in todays:
                tasks.append({**t, "workspace_id": ws["id"], "workspace_name": ws.get("name")})
            summaries.append({
                "workspace_id": ws["id"],
                "workspace_name": ws.get("name"),
                "target_date": plan.get("target_date"),
                "days_remaining": plan.get("days_remaining"),
                "target_passed": plan.get("target_passed"),
                "daily_target_minutes": plan.get("daily_target_minutes"),
                "today_completed_minutes": plan.get("today_completed_minutes"),
                "today_planned_minutes": plan.get("today_planned_minutes"),
                "open_tasks": sum(1 for t in todays if not t.get("completed")),
                "on_track": plan.get("on_track"),
                "needed_daily_minutes": plan.get("needed_daily_minutes"),
            })

        # Open tasks first (high priority, then carried over), then the ones already done
        prio = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda t: (
            bool(t.get("completed")),
            prio.get(str(t.get("priority")), 1),
            not t.get("carriedOver"),
        ))
        return {
            "date": today.isoformat(),
            "planned_minutes": sum(int(t.get("estimatedMinutes") or 0) for t in tasks),
            "completed_minutes": sum(s.get("today_completed_minutes") or 0 for s in summaries),
            "daily_target_minutes": sum(
                int(s.get("daily_target_minutes") or 0) for s in summaries if not s.get("target_passed")
            ),
            "open_tasks": sum(1 for t in tasks if not t.get("completed")),
            "tasks": tasks,
            "workspaces": summaries,
        }


study_plan_service = StudyPlanService()
