"""
Day-by-day study planner.

The plan spreads every concept of the workspace's topic map over the days left until the target
completion date, within the learner's daily study minutes:

- Weak spots found by the adaptive quiz (BKT knowledge gaps) come first, as review tasks.
- Concepts that are still developing get a practice quiz.
- Concepts not studied yet get a "learn" task (in topic-map order), then a check quiz the next day.
- Flashcards due on a day become one review task for that day.
- The target day ends with a final adaptive quiz.

Today's tasks are frozen in a snapshot when the day's plan is first built, so the list stays stable
while the learner works through it; later days are recomputed on every request from the latest
results. Completions are stored with their date, so today's and this week's minutes reset by
themselves, and unfinished tasks from earlier days are carried into the next day's plan.

This module is pure (no I/O) so the scheduling rules can be tested directly.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

# Minutes per task kind
LEARN_MINUTES = 15
PRACTICE_MINUTES = 10
REVIEW_MINUTES = 20
FINAL_MINUTES = 25
FLASHCARD_MINUTES_PER_CARD = 1
FLASHCARD_MIN_MINUTES = 5
FLASHCARD_MAX_MINUTES = 20

# A concept counts as mastered from this BKT probability (same band as the analytics page)
MASTERED_P = 0.75
# Gap statuses that need a review (the others only need practice, or nothing for "strong")
REVIEW_STATUSES = ("critical_gap", "needs_attention")
DONE_STATUSES = ("strong", "resolved")

# Days before a reviewed or practised concept is scheduled again, unless a newer quiz result
# says it is still weak (then it can come back the next day)
REVISIT_AFTER_DAYS = 2
NO_TARGET_HORIZON_DAYS = 30
MAX_HORIZON_DAYS = 366
MAX_DAILY_MINUTES = 600
WEEK_LENGTH = 7


def slug(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:10]


def flashcard_minutes(count: int) -> int:
    return max(FLASHCARD_MIN_MINUTES, min(FLASHCARD_MAX_MINUTES, count * FLASHCARD_MINUTES_PER_CARD))


@dataclass
class ConceptState:
    concept: str
    topic: str
    position: int = 0
    p_mastery: Optional[float] = None  # None: never quizzed
    gap_status: Optional[str] = None
    gap_priority: float = 0.0
    evidence_at: Optional[datetime] = None  # last quiz answer on this concept (UTC)

    @property
    def key(self) -> str:
        return self.concept.strip().lower()


@dataclass
class PlanInputs:
    today: date
    target_date: Optional[date]
    daily_minutes: int
    concepts: List[ConceptState]
    has_documents: bool
    # Flashcards due per day; the entry for `today` includes overdue and never-reviewed cards
    flashcards_due: Dict[date, int] = field(default_factory=dict)
    flashcards_reviewed_today: int = 0
    completions: List[Dict[str, Any]] = field(default_factory=list)
    # Today's frozen task list, if it was already built today
    snapshot: Optional[List[Dict[str, Any]]] = None
    snapshot_at: Optional[datetime] = None
    # Yesterday's (or the last earlier) snapshot, to mark carried-over tasks
    previous_snapshot: Optional[List[Dict[str, Any]]] = None
    workspace_id: str = ""
    tz_offset_minutes: int = 0
    now: Optional[datetime] = None  # UTC, for auto-completions
    # When today's list is rebuilt on request: the tasks already done today, kept at the top
    keep_today: List[Dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------

def local_date(ts: Optional[datetime], tz_offset_minutes: int) -> Optional[date]:
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return None
    return (ts + timedelta(minutes=tz_offset_minutes)).date()


def _as_dt(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _href(workspace_id: str, page: str, ask: Optional[str] = None) -> str:
    base = f"/dashboard/workspace/{workspace_id}/{page}"
    return f"{base}?ask={quote(ask)}" if ask else base


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _bucket(day: date, today: date) -> str:
    if day <= today:
        return "today"
    if (day - today).days < WEEK_LENGTH:
        return "this_week"
    return "upcoming"


# --------------------------------------------------------------------------------------------
# Task builders
# --------------------------------------------------------------------------------------------

def _concept_task(kind: str, c: ConceptState, instance: int, inputs: PlanInputs, learned_untested: bool = False) -> Dict[str, Any]:
    ws = inputs.workspace_id
    base_id = f"{kind}-{slug(c.concept)}"
    task_id = base_id if kind == "learn" else f"{base_id}-{instance}"
    mastery_pct = None if c.p_mastery is None else round(c.p_mastery * 100)

    if kind == "learn":
        title = f"Learn: {c.concept}"
        description = f"Read about {c.concept} in your notes and ask the tutor anything that is unclear."
        action, href = "tutor", _href(ws, "tutor", f"Explain \"{c.concept}\" from my notes with a simple example.")
        minutes, priority = LEARN_MINUTES, "medium"
    elif kind == "review":
        title = f"Fix weak spot: {c.concept}"
        description = (
            f"Your quiz answers show a gap in {c.concept} (gap priority {round(c.gap_priority * 100)}%). "
            "Revise it with the tutor, then take a quiz to check it."
        )
        action = "tutor"
        href = _href(ws, "tutor", f"I keep getting \"{c.concept}\" wrong. Explain it simply from my notes.")
        minutes = REVIEW_MINUTES
        priority = "high" if c.gap_priority >= 0.6 or c.gap_status == "critical_gap" else "medium"
    else:  # practice
        title = f"Practise: {c.concept}"
        description = (
            f"Check what you learned about {c.concept} with a short adaptive quiz."
            if learned_untested or mastery_pct is None
            else f"Strengthen {c.concept} with a short adaptive quiz. Current mastery: {mastery_pct}%."
        )
        action, href = "quiz", _href(ws, "quiz")
        minutes, priority = PRACTICE_MINUTES, "medium"

    return {
        "id": task_id,
        "kind": kind,
        "title": title,
        "description": description,
        "estimatedMinutes": minutes,
        "tag": c.concept,
        "concept": c.concept,
        "topic": c.topic,
        "action": action,
        "href": href,
        "priority": priority,
    }


def _flashcard_task(day: date, count: int, inputs: PlanInputs) -> Dict[str, Any]:
    return {
        "id": f"flash-{day.isoformat()}",
        "kind": "flashcards",
        "title": f"Review {count} flashcard{'s' if count != 1 else ''}",
        "description": "Spaced-repetition review keeps what you have learned from fading.",
        "estimatedMinutes": flashcard_minutes(count),
        "tag": "Flashcards",
        "concept": None,
        "topic": None,
        "action": "flashcards",
        "href": _href(inputs.workspace_id, "flashcards"),
        "priority": "medium",
        "cardCount": count,
    }


def _final_task(day: date, inputs: PlanInputs) -> Dict[str, Any]:
    return {
        "id": f"final-{day.isoformat()}",
        "kind": "final",
        "title": "Final check: full adaptive quiz",
        "description": "Your target date is here. Take a full adaptive quiz to confirm everything is mastered.",
        "estimatedMinutes": FINAL_MINUTES,
        "tag": "Final check",
        "concept": None,
        "topic": None,
        "action": "quiz",
        "href": _href(inputs.workspace_id, "quiz"),
        "priority": "high",
    }


def _starter_tasks(inputs: PlanInputs) -> List[Dict[str, Any]]:
    ws = inputs.workspace_id
    if not inputs.has_documents:
        return [{
            "id": "start-upload",
            "kind": "setup",
            "title": "Upload your notes",
            "description": "Add your PDF, Word, PowerPoint or text notes. Your plan is built from the topics in them.",
            "estimatedMinutes": 5,
            "tag": "Getting started",
            "concept": None,
            "topic": None,
            "action": "sources",
            "href": _href(ws, "sources"),
            "priority": "high",
        }]
    return [
        {
            "id": "start-diagnostic",
            "kind": "setup",
            "title": "Take a diagnostic quiz",
            "description": "A short adaptive quiz finds what you already know, so the plan can focus on the rest.",
            "estimatedMinutes": 15,
            "tag": "Diagnostic",
            "concept": None,
            "topic": None,
            "action": "quiz",
            "href": _href(ws, "quiz"),
            "priority": "high",
        },
        {
            "id": "start-explore",
            "kind": "setup",
            "title": "Explore your notes with the tutor",
            "description": "Your topic map is still being prepared. Meanwhile, ask the tutor for a summary of your notes.",
            "estimatedMinutes": 15,
            "tag": "Fundamentals",
            "concept": None,
            "topic": None,
            "action": "tutor",
            "href": _href(ws, "tutor", "Give me a short summary of the main topics in my notes."),
            "priority": "medium",
        },
    ]


# --------------------------------------------------------------------------------------------
# Work queue
# --------------------------------------------------------------------------------------------

@dataclass
class QueueItem:
    task: Dict[str, Any]
    eligible_from: date
    order: Tuple[int, float, int]
    # Task that becomes due the day after this one is scheduled (a learn task's check quiz)
    followup: Optional[Dict[str, Any]] = None


def _completions_by_task(completions: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for comp in completions:
        out.setdefault(str(comp.get("task_id")), []).append(comp)
    return out


def _concept_completions(completions: Iterable[Dict[str, Any]], concept_key: str, kinds: Tuple[str, ...]) -> List[Dict[str, Any]]:
    return [
        comp for comp in completions
        if comp.get("kind") in kinds and str(comp.get("concept") or "").strip().lower() == concept_key
    ]


def build_queue(inputs: PlanInputs, exclude_keys: Optional[set] = None) -> List[QueueItem]:
    """Every concept task still needed, in priority order, with the first day it may be scheduled."""
    exclude_keys = exclude_keys or set()
    today = inputs.today
    items: List[QueueItem] = []

    for c in inputs.concepts:
        if c.key in exclude_keys:
            continue
        learn_done = _concept_completions(inputs.completions, c.key, ("learn",))
        practice_done = _concept_completions(inputs.completions, c.key, ("practice", "review"))
        quizzed = c.p_mastery is not None

        if quizzed:
            status = c.gap_status
            if status in DONE_STATUSES or (status not in REVIEW_STATUSES and (c.p_mastery or 0) >= MASTERED_P):
                continue
            kind = "review" if status in REVIEW_STATUSES else "practice"
            last = max(practice_done, key=lambda x: str(x.get("at") or x.get("date"))) if practice_done else None
            eligible = today
            if last:
                last_day = date.fromisoformat(str(last["date"]))
                last_at = _as_dt(last.get("at"))
                newer_evidence = bool(c.evidence_at and last_at and c.evidence_at > last_at)
                eligible = max(today, last_day + timedelta(days=1 if newer_evidence else REVISIT_AFTER_DAYS))
            elif kind == "practice" and local_date(c.evidence_at, inputs.tz_offset_minutes) == today:
                eligible = today + timedelta(days=1)  # already quizzed on it today
            instance = len(_concept_completions(inputs.completions, c.key, (kind,))) + 1
            task = _concept_task(kind, c, instance, inputs)
            if kind == "review":
                order = (0, -c.gap_priority, c.position)
            else:
                order = (1, c.p_mastery or 0.0, c.position)
            items.append(QueueItem(task, eligible, order))
        elif learn_done:
            # Learned but not quizzed yet: a check quiz from the day after it was learned
            learned_on = min(date.fromisoformat(str(x["date"])) for x in learn_done)
            if practice_done:
                continue  # practised already; the next quiz result will decide what comes next
            task = _concept_task("practice", c, 1, inputs, learned_untested=True)
            items.append(QueueItem(task, max(today, learned_on + timedelta(days=1)), (2, 0.0, c.position)))
        else:
            task = _concept_task("learn", c, 1, inputs)
            check = _concept_task("practice", c, 1, inputs, learned_untested=True)
            items.append(QueueItem(task, today, (3, 0.0, c.position), followup=check))

    items.sort(key=lambda it: it.order)
    return items


# --------------------------------------------------------------------------------------------
# Scheduling
# --------------------------------------------------------------------------------------------

def _horizon(inputs: PlanInputs) -> List[date]:
    today = inputs.today
    end = inputs.target_date or (today + timedelta(days=NO_TARGET_HORIZON_DAYS))
    end = min(end, today + timedelta(days=MAX_HORIZON_DAYS))
    days = (end - today).days + 1
    return [today + timedelta(days=i) for i in range(max(1, days))]


def _fill_days(
    days: List[date],
    queue: List[QueueItem],
    capacity: int,
    fixed: Dict[date, List[Dict[str, Any]]],
) -> Tuple[Dict[date, List[Dict[str, Any]]], List[QueueItem]]:
    """Greedy fill: each day takes the highest-priority eligible tasks that fit its minutes.

    A day always takes at least one task when it has room left, even if that task is longer than
    the room, so a short daily target never blocks the plan.
    """
    schedule: Dict[date, List[Dict[str, Any]]] = {d: [dict(t) for t in fixed.get(d, [])] for d in days}
    remaining = list(queue)
    for d in days:
        remaining.sort(key=lambda it: it.order)
        used = sum(t["estimatedMinutes"] for t in schedule[d])
        took_any = False
        still: List[QueueItem] = []
        for item in remaining:
            minutes = item.task["estimatedMinutes"]
            fits = (used + minutes <= capacity) or (not took_any and used < capacity)
            if item.eligible_from <= d and fits:
                schedule[d].append(dict(item.task))
                used += minutes
                took_any = True
                if item.followup:
                    position = item.order[2]
                    still.append(QueueItem(dict(item.followup), d + timedelta(days=1), (2, 0.0, position)))
            else:
                still.append(item)
        remaining = still
    return schedule, remaining


def _schedule(
    days: List[date],
    queue: List[QueueItem],
    daily: int,
    fixed: Dict[date, List[Dict[str, Any]]],
) -> Tuple[Dict[date, List[Dict[str, Any]]], int]:
    """Schedules the queue over the days. If it doesn't fit in the daily minutes before the last day,
    finds the smallest daily load (in 5-minute steps) that fits; returns the schedule and that load."""
    schedule, leftover = _fill_days(days, queue, daily, fixed)
    if not leftover:
        return schedule, daily
    # Binary search over daily + 5k minutes, up to MAX_DAILY_MINUTES
    lo, hi = 1, max(1, (MAX_DAILY_MINUTES - daily) // 5)
    best = None
    while lo <= hi:
        k = (lo + hi) // 2
        trial, left = _fill_days(days, queue, daily + 5 * k, fixed)
        if not left:
            best = (trial, daily + 5 * k)
            hi = k - 1
        else:
            lo = k + 1
    if best:
        return best
    # Still doesn't fit (for example, only one day left): the rest goes on the last day
    cap = max(daily, MAX_DAILY_MINUTES)
    schedule, leftover = _fill_days(days, queue, cap, fixed)
    schedule[days[-1]].extend(dict(it.task) for it in leftover)
    return schedule, cap


def _concept_key(task: Dict[str, Any]) -> str:
    return str(task.get("concept") or "").strip().lower()


def build_plan(inputs: PlanInputs) -> Dict[str, Any]:
    """Builds the full plan: today's tasks, later days, totals and any new auto-completions."""
    today = inputs.today
    today_iso = today.isoformat()
    tz = inputs.tz_offset_minutes
    days = _horizon(inputs)
    daily = max(10, int(inputs.daily_minutes or 45))
    has_concepts = bool(inputs.concepts)
    concepts_by_key = {c.key: c for c in inputs.concepts}
    final_day = inputs.target_date if inputs.target_date and inputs.target_date == days[-1] else None

    def fixed_tasks(for_days: List[date]) -> Dict[date, List[Dict[str, Any]]]:
        fixed: Dict[date, List[Dict[str, Any]]] = {}
        for d in for_days:
            n = inputs.flashcards_due.get(d, 0)
            if n > 0:
                fixed.setdefault(d, []).append(_flashcard_task(d, n, inputs))
        if has_concepts and final_day and final_day in for_days and (len(days) >= 3 or final_day == today):
            fixed.setdefault(final_day, []).append(_final_task(final_day, inputs))
        return fixed

    completed_today_ids = {
        str(c.get("task_id")) for c in inputs.completions if str(c.get("date")) == today_iso
    }

    # ---- Today's list: the snapshot built earlier today, or a new one ----
    snapshot = inputs.snapshot
    starter_only = bool(snapshot) and all(t.get("kind") == "setup" for t in snapshot or [])
    rebuild_today = snapshot is None or (starter_only and has_concepts)
    flash_today = inputs.flashcards_due.get(today, 0)

    if rebuild_today:
        kept = [dict(t) for t in inputs.keep_today]
        kept_ids = {t.get("id") for t in kept}
        if has_concepts:
            queue = build_queue(inputs)
            full, capacity = _schedule(days, queue, daily, fixed_tasks(days))
            today_tasks = full[today]
            if kept:
                # Rebuilt on request: keep what's done and add at least one new task
                fixed_today = kept + [t for t in fixed_tasks([today]).get(today, []) if t["id"] not in kept_ids]
                used = sum(int(t.get("estimatedMinutes") or 0) for t in fixed_today)
                queue = [it for it in queue if it.task["id"] not in kept_ids]
                filled, _ = _fill_days([today], queue, max(capacity, used + 1), {today: fixed_today})
                today_tasks = filled[today]
        else:
            today_tasks = kept + [
                t for t in fixed_tasks([today]).get(today, []) + _starter_tasks(inputs) if t["id"] not in kept_ids
            ]
        prev_ids = {t.get("id") for t in (inputs.previous_snapshot or [])}
        for t in today_tasks:
            t["carriedOver"] = t["id"] in prev_ids
        snapshot_at = inputs.now
    else:
        today_tasks = [dict(t) for t in snapshot or []]
        snapshot_at = inputs.snapshot_at
        if flash_today > 0 and not any(t.get("kind") == "flashcards" for t in today_tasks):
            today_tasks.insert(0, _flashcard_task(today, flash_today, inputs))

    # ---- Auto-complete today's tasks already done elsewhere in the app ----
    new_completions: List[Dict[str, Any]] = []
    for t in today_tasks:
        if t["id"] in completed_today_ids or t.get("noAuto"):
            continue
        done_at: Optional[datetime] = None
        if t.get("kind") == "flashcards":
            if flash_today == 0 and inputs.flashcards_reviewed_today > 0:
                done_at = inputs.now
        elif t.get("kind") in ("learn", "practice", "review") and t.get("concept"):
            c = concepts_by_key.get(_concept_key(t))
            if c and c.evidence_at and local_date(c.evidence_at, tz) == today:
                if snapshot_at is None or c.evidence_at >= snapshot_at:
                    done_at = c.evidence_at
        if done_at is not None:
            new_completions.append(completion_record(t, today, done_at, auto=True))
            completed_today_ids.add(t["id"])

    all_completions = list(inputs.completions) + new_completions
    for t in today_tasks:
        t["completed"] = t["id"] in completed_today_ids
        t["scheduledDate"] = today_iso
        t["scheduledFor"] = "today"
        t.setdefault("carriedOver", False)
        if t["completed"]:
            t["carriedOver"] = False

    # ---- Later days, recomputed from the latest results ----
    later_days = days[1:]
    later_tasks: List[Dict[str, Any]] = []
    needed_daily = daily
    if has_concepts and later_days:
        open_today = {_concept_key(t) for t in today_tasks if t.get("concept") and not t["completed"]}
        future_inputs = PlanInputs(**{**inputs.__dict__, "completions": all_completions})
        queue = build_queue(future_inputs, exclude_keys=open_today)
        # A concept learned today gets its check quiz from tomorrow
        for t in today_tasks:
            if t.get("kind") == "learn" and not t["completed"]:
                c = concepts_by_key.get(_concept_key(t))
                if c:
                    queue.append(QueueItem(
                        _concept_task("practice", c, 1, inputs, learned_untested=True),
                        today + timedelta(days=1),
                        (2, 0.0, c.position),
                    ))
        queue.sort(key=lambda it: it.order)
        schedule, needed_daily = _schedule(later_days, queue, daily, fixed_tasks(later_days))
        for d in later_days:
            for t in schedule[d]:
                t.update(completed=False, carriedOver=False, scheduledDate=d.isoformat(), scheduledFor=_bucket(d, today))
                later_tasks.append(t)
    elif later_days:
        for d, tasks in fixed_tasks(later_days).items():
            for t in tasks:
                t.update(completed=False, carriedOver=False, scheduledDate=d.isoformat(), scheduledFor=_bucket(d, today))
                later_tasks.append(t)
        later_tasks.sort(key=lambda t: t["scheduledDate"])

    # ---- Totals ----
    week_start = _week_start(today)
    today_minutes = sum(int(c.get("minutes") or 0) for c in all_completions if str(c.get("date")) == today_iso)
    week_minutes = 0
    for c in all_completions:
        try:
            if week_start <= date.fromisoformat(str(c.get("date"))) <= today:
                week_minutes += int(c.get("minutes") or 0)
        except ValueError:
            continue

    finish = None
    if has_concepts:
        concept_days = [t["scheduledDate"] for t in later_tasks if t.get("kind") in ("learn", "practice", "review")]
        if concept_days:
            finish = max(concept_days)
        elif any(not t["completed"] and t.get("kind") in ("learn", "practice", "review") for t in today_tasks):
            finish = today_iso

    mastered = in_progress = not_started = 0
    for c in inputs.concepts:
        if c.p_mastery is None:
            not_started += 1
        elif c.gap_status in DONE_STATUSES or (c.gap_status not in REVIEW_STATUSES and c.p_mastery >= MASTERED_P):
            mastered += 1
        else:
            in_progress += 1

    return {
        "today_tasks": today_tasks,
        "later_tasks": later_tasks,
        "snapshot": [
            {k: v for k, v in t.items() if k not in ("completed", "scheduledDate", "scheduledFor")}
            for t in today_tasks
        ],
        "snapshot_rebuilt": rebuild_today,
        "snapshot_at": snapshot_at,
        "new_completions": new_completions,
        "daily_target_minutes": daily,
        "weekly_target_minutes": daily * WEEK_LENGTH,
        "today_completed_minutes": today_minutes,
        "week_completed_minutes": week_minutes,
        "today_planned_minutes": sum(int(t.get("estimatedMinutes") or 0) for t in today_tasks),
        "needed_daily_minutes": needed_daily,
        "on_track": needed_daily <= daily,
        "expected_finish_date": finish,
        "coverage": {
            "total_concepts": len(inputs.concepts),
            "mastered": mastered,
            "in_progress": in_progress,
            "not_started": not_started,
        },
    }


def completion_record(task: Dict[str, Any], day: date, at: datetime, auto: bool = False) -> Dict[str, Any]:
    return {
        "task_id": task["id"],
        "kind": task.get("kind"),
        "concept": task.get("concept"),
        "title": task.get("title"),
        "date": day.isoformat(),
        "minutes": int(task.get("estimatedMinutes") or 0),
        "at": at.isoformat(),
        "auto": auto,
    }


def find_task(plan: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for t in plan.get("today_tasks", []) + plan.get("later_tasks", []):
        if t.get("id") == task_id:
            return t
    return None
