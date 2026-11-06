"""
Day-by-day study plan.

Planner rules (pure, tested directly) and the API on top of them: topic-wise scheduling up to the
target date, weak spots first, counters that reset by date, a stable list for the day, carried-over
tasks, auto-ticking, working ahead, and the combined "today" view across workspaces.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.concepts import concept_repo
from backend.app.repositories.workspaces import workspace_repo
from backend.app.services import study_planner as planner
from backend.app.services.study_plan_service import study_plan_service

TODAY = date(2026, 11, 9)  # a Monday
NOW = datetime(2026, 11, 9, 4, 0, tzinfo=timezone.utc)


def _concepts(n: int, topic: str = "Memory"):
    return [planner.ConceptState(concept=f"Concept {i + 1}", topic=topic, position=i) for i in range(n)]


def _inputs(**kw):
    base = dict(
        today=TODAY,
        target_date=TODAY + timedelta(days=13),
        daily_minutes=45,
        concepts=_concepts(6),
        has_documents=True,
        workspace_id="ws_t",
        tz_offset_minutes=330,
        now=NOW,
    )
    base.update(kw)
    return planner.PlanInputs(**base)


def _all(plan):
    return plan["today_tasks"] + plan["later_tasks"]


# ------------------------------------------------------------------ planner rules

def test_every_concept_is_scheduled_topic_wise_within_the_daily_minutes():
    plan = planner.build_plan(_inputs())
    learn = [t for t in _all(plan) if t["kind"] == "learn"]
    assert [t["concept"] for t in learn] == [f"Concept {i + 1}" for i in range(6)]  # topic-map order
    assert all(t["topic"] == "Memory" for t in learn)
    # Each day stays within 45 minutes
    per_day = {}
    for t in _all(plan):
        per_day[t["scheduledDate"]] = per_day.get(t["scheduledDate"], 0) + t["estimatedMinutes"]
    assert max(per_day.values()) <= 45
    assert plan["on_track"] is True and plan["needed_daily_minutes"] == 45
    # Real dates, never before today or after the target date
    dates = sorted({t["scheduledDate"] for t in _all(plan)})
    assert dates[0] == TODAY.isoformat()
    assert dates[-1] <= (TODAY + timedelta(days=13)).isoformat()


def test_a_check_quiz_follows_each_learn_task_on_a_later_day():
    plan = planner.build_plan(_inputs())
    learn_day = {t["concept"]: t["scheduledDate"] for t in _all(plan) if t["kind"] == "learn"}
    practice_day = {t["concept"]: t["scheduledDate"] for t in _all(plan) if t["kind"] == "practice"}
    assert set(practice_day) == set(learn_day)
    for concept, day in learn_day.items():
        assert practice_day[concept] > day


def test_weak_spots_come_first_and_mastered_concepts_are_skipped():
    concepts = _concepts(4)
    concepts[2].p_mastery, concepts[2].gap_status, concepts[2].gap_priority = 0.2, "critical_gap", 0.9
    concepts[3].p_mastery, concepts[3].gap_status = 0.9, "strong"
    plan = planner.build_plan(_inputs(concepts=concepts))
    first = plan["today_tasks"][0]
    assert first["kind"] == "review" and first["concept"] == "Concept 3" and first["priority"] == "high"
    assert first["action"] == "tutor" and "ask=" in first["href"]
    assert not any(t["concept"] == "Concept 4" for t in _all(plan))
    assert plan["coverage"] == {"total_concepts": 4, "mastered": 1, "in_progress": 1, "not_started": 2}


def test_developing_concepts_get_a_practice_quiz():
    concepts = _concepts(1)
    concepts[0].p_mastery, concepts[0].gap_status = 0.6, "developing"
    plan = planner.build_plan(_inputs(concepts=concepts))
    task = plan["today_tasks"][0]
    assert task["kind"] == "practice" and task["action"] == "quiz" and "60%" in task["description"]


def test_behind_schedule_raises_the_daily_load_to_finish_by_the_target_date():
    plan = planner.build_plan(_inputs(concepts=_concepts(20), target_date=TODAY + timedelta(days=3)))
    assert plan["on_track"] is False
    assert plan["needed_daily_minutes"] > 45
    learned = {t["concept"] for t in _all(plan) if t["kind"] == "learn"}
    assert len(learned) == 20  # nothing is dropped
    assert plan["expected_finish_date"] <= (TODAY + timedelta(days=3)).isoformat()


def test_the_target_day_ends_with_a_final_quiz():
    target = TODAY + timedelta(days=5)
    plan = planner.build_plan(_inputs(target_date=target))
    finals = [t for t in _all(plan) if t["kind"] == "final"]
    assert len(finals) == 1 and finals[0]["scheduledDate"] == target.isoformat()


def test_flashcards_due_become_a_task_on_their_day():
    due = {TODAY: 12, TODAY + timedelta(days=2): 3}
    plan = planner.build_plan(_inputs(flashcards_due=due))
    today_flash = [t for t in plan["today_tasks"] if t["kind"] == "flashcards"]
    assert today_flash and today_flash[0]["title"] == "Review 12 flashcards" and today_flash[0]["estimatedMinutes"] == 12
    later = [t for t in plan["later_tasks"] if t["kind"] == "flashcards"]
    assert [(t["scheduledDate"], t["cardCount"]) for t in later] == [((TODAY + timedelta(days=2)).isoformat(), 3)]


def test_starter_tasks_until_there_is_a_topic_map():
    no_docs = planner.build_plan(_inputs(concepts=[], has_documents=False))
    assert [t["title"] for t in no_docs["today_tasks"]] == ["Upload your notes"]
    with_docs = planner.build_plan(_inputs(concepts=[]))
    assert [t["id"] for t in with_docs["today_tasks"]] == ["start-diagnostic", "start-explore"]


def test_minutes_come_from_dated_completions_and_reset_by_day_and_week():
    comps = [
        {"task_id": "a", "date": TODAY.isoformat(), "minutes": 15, "at": NOW.isoformat()},
        {"task_id": "b", "date": (TODAY - timedelta(days=1)).isoformat(), "minutes": 20, "at": NOW.isoformat()},
    ]
    plan = planner.build_plan(_inputs(completions=comps))
    assert plan["today_completed_minutes"] == 15
    assert plan["week_completed_minutes"] == 15  # Sunday's minutes belong to last week
    tomorrow = planner.build_plan(_inputs(today=TODAY + timedelta(days=1), completions=comps))
    assert tomorrow["today_completed_minutes"] == 0
    assert tomorrow["week_completed_minutes"] == 15


def test_todays_list_is_frozen_and_auto_ticks_after_a_quiz():
    first = planner.build_plan(_inputs())
    snapshot = first["snapshot"]
    concept = first["today_tasks"][0]["concept"]

    concepts = _concepts(6)
    for c in concepts:
        if c.concept == concept:
            c.p_mastery, c.gap_status, c.evidence_at = 0.8, "strong", NOW + timedelta(hours=1)
    later = planner.build_plan(_inputs(concepts=concepts, snapshot=snapshot, snapshot_at=NOW, now=NOW + timedelta(hours=2)))
    assert [t["id"] for t in later["today_tasks"]] == [t["id"] for t in first["today_tasks"]]
    assert later["today_tasks"][0]["completed"] is True
    assert later["new_completions"][0]["auto"] is True


def test_an_unticked_task_is_not_auto_ticked_again():
    first = planner.build_plan(_inputs())
    snapshot = [dict(t, noAuto=True) for t in first["snapshot"]]
    concepts = _concepts(6)
    concepts[0].p_mastery, concepts[0].evidence_at = 0.8, NOW + timedelta(hours=1)
    later = planner.build_plan(_inputs(concepts=concepts, snapshot=snapshot, snapshot_at=NOW))
    assert later["new_completions"] == []


def test_unfinished_tasks_are_carried_into_the_next_day():
    day1 = planner.build_plan(_inputs())
    day2 = planner.build_plan(_inputs(today=TODAY + timedelta(days=1), previous_snapshot=day1["snapshot"]))
    carried = [t for t in day2["today_tasks"] if t["carriedOver"]]
    assert carried and carried[0]["id"] == day1["today_tasks"][0]["id"]


def test_completed_learn_task_is_not_repeated_and_its_quiz_comes_next_day():
    day1 = planner.build_plan(_inputs())
    task = day1["today_tasks"][0]
    comp = planner.completion_record(task, TODAY, NOW)
    day2 = planner.build_plan(_inputs(today=TODAY + timedelta(days=1), completions=[comp]))
    ids = [t["id"] for t in _all(day2)]
    assert task["id"] not in ids
    practice = [t for t in day2["today_tasks"] if t["kind"] == "practice" and t["concept"] == task["concept"]]
    assert practice


def test_rebuilding_today_keeps_done_tasks_and_adds_more():
    day = planner.build_plan(_inputs())
    done = day["today_tasks"]
    comps = [planner.completion_record(t, TODAY, NOW) for t in done]
    more = planner.build_plan(_inputs(completions=comps, keep_today=day["snapshot"]))
    ids = [t["id"] for t in more["today_tasks"]]
    assert ids[: len(done)] == [t["id"] for t in done]
    assert len(ids) > len(done)
    assert all(t["completed"] for t in more["today_tasks"][: len(done)])


# ------------------------------------------------------------------ API

async def _workspace(client, name="Operating Systems", days=13, minutes=45) -> str:
    res = await client.post(
        "/api/v1/workspaces",
        json={
            "name": f"{name} {uuid.uuid4().hex[:4]}",
            "goal": "Learn it",
            "level": "beginner",
            "target_date": (date.today() + timedelta(days=days)).isoformat(),
            "daily_target_minutes": minutes,
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


async def _topic_map(ws_id: str, names):
    await workspace_repo.increment_doc_count(ws_id, 1)
    await concept_repo.replace_for_document(
        ws_id, f"doc_{uuid.uuid4().hex[:6]}", "notes.pdf",
        [{"topic": "Memory", "concept": n, "summary": "", "key_points": []} for n in names],
    )


async def _plan(client, ws_id):
    res = await client.get(f"/api/v1/workspaces/{ws_id}/study-plan")
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_api_plan_is_topic_wise_with_dates(async_client):
    ws_id = await _workspace(async_client)
    empty = await _plan(async_client, ws_id)
    assert [t["title"] for t in empty["tasks"]] == ["Upload your notes"]

    await _topic_map(ws_id, ["Paging", "Segmentation", "TLB", "Page replacement"])
    plan = await _plan(async_client, ws_id)
    titles = [t["title"] for t in plan["tasks"]]
    assert titles[0] == "Learn: Paging"  # starter list replaced as soon as the topic map exists
    assert {"Learn: Paging", "Learn: Segmentation", "Learn: TLB", "Learn: Page replacement"} <= set(titles)
    assert all(t["scheduledDate"] for t in plan["tasks"])
    assert plan["coverage"]["total_concepts"] == 4
    assert plan["expected_finish_date"] is not None


@pytest.mark.asyncio
async def test_api_tick_untick_and_minutes(async_client):
    ws_id = await _workspace(async_client)
    await _topic_map(ws_id, ["Paging", "TLB"])
    plan = await _plan(async_client, ws_id)
    task = next(t for t in plan["tasks"] if t["scheduledFor"] == "today")

    ticked = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/tasks/{task['id']}/toggle")
    assert ticked.status_code == 200
    body = ticked.json()
    assert body["today_completed_minutes"] == task["estimatedMinutes"]
    assert next(t for t in body["tasks"] if t["id"] == task["id"])["completed"] is True

    unticked = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/tasks/{task['id']}/toggle")
    assert unticked.json()["today_completed_minutes"] == 0

    missing = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/tasks/nope/toggle")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_api_working_ahead_moves_the_task_into_today(async_client):
    ws_id = await _workspace(async_client, minutes=15)
    await _topic_map(ws_id, ["Paging", "TLB", "Segmentation"])
    plan = await _plan(async_client, ws_id)
    later = next(t for t in plan["tasks"] if t["scheduledFor"] != "today" and t["kind"] == "learn")
    res = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/tasks/{later['id']}/toggle")
    assert res.status_code == 200
    moved = next(t for t in res.json()["tasks"] if t["id"] == later["id"])
    assert moved["scheduledFor"] == "today" and moved["completed"] is True and moved["doneAhead"] is True


@pytest.mark.asyncio
async def test_api_list_is_stable_and_quiz_results_shape_later_days(async_client):
    ws_id = await _workspace(async_client)
    await _topic_map(ws_id, ["Paging", "TLB", "Segmentation", "Thrashing", "Swapping"])
    first = await _plan(async_client, ws_id)
    today_ids = [t["id"] for t in first["tasks"] if t["scheduledFor"] == "today"]

    await bkt_repo.upsert_knowledge_gap(ws_id, "Memory", "Swapping", 0.9, "critical_gap", {})
    await bkt_repo.upsert_concept_mastery(ws_id, "Memory", "Swapping", 0.2, False)
    second = await _plan(async_client, ws_id)
    assert [t["id"] for t in second["tasks"] if t["scheduledFor"] == "today"] == today_ids
    tomorrow = [t for t in second["tasks"] if t["scheduledFor"] != "today"]
    assert tomorrow[0]["kind"] == "review" and tomorrow[0]["concept"] == "Swapping"

    # "Plan more for today" rebuilds today's list from the latest results
    rebuilt = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/generate")
    assert rebuilt.status_code == 201
    assert rebuilt.json()["tasks"][0]["concept"] == "Swapping"


@pytest.mark.asyncio
async def test_api_changing_the_daily_minutes_rebuilds_today(async_client):
    ws_id = await _workspace(async_client, minutes=15)
    await _topic_map(ws_id, [f"Concept {i}" for i in range(8)])
    small = await _plan(async_client, ws_id)
    n_small = sum(1 for t in small["tasks"] if t["scheduledFor"] == "today")
    res = await async_client.patch(f"/api/v1/workspaces/{ws_id}", json={"daily_target_minutes": 90})
    assert res.status_code == 200
    big = await _plan(async_client, ws_id)
    assert sum(1 for t in big["tasks"] if t["scheduledFor"] == "today") > n_small


@pytest.mark.asyncio
async def test_api_today_overview_combines_the_users_workspaces_only(async_client):
    a = await _workspace(async_client, name="Networks")
    b = await _workspace(async_client, name="DBMS")
    await _topic_map(a, ["TCP", "UDP"])
    await _topic_map(b, ["Normalization"])
    # Someone else's workspace never shows up
    other = f"ws_other_{uuid.uuid4().hex[:6]}"
    await workspace_repo.create(workspace_id=other, name="Private", goal="x", level="beginner", owner_id="usr_someone_else")
    await _topic_map(other, ["Secret"])

    res = await async_client.get("/api/v1/study-plan/today")
    assert res.status_code == 200
    body = res.json()
    done_before = body["completed_minutes"]
    ws_ids = {t["workspace_id"] for t in body["tasks"]}
    assert {a, b} <= ws_ids and other not in ws_ids
    assert all(t["scheduledFor"] == "today" for t in body["tasks"])
    assert body["planned_minutes"] == sum(t["estimatedMinutes"] for t in body["tasks"])
    assert {s["workspace_id"] for s in body["workspaces"]} >= {a, b}

    # Ticking from the dashboard updates the right workspace
    t = next(t for t in body["tasks"] if t["workspace_id"] == b)
    await async_client.post(f"/api/v1/workspaces/{b}/study-plan/tasks/{t['id']}/toggle")
    after = (await async_client.get("/api/v1/study-plan/today")).json()
    assert next(x for x in after["tasks"] if x["id"] == t["id"] and x["workspace_id"] == b)["completed"] is True
    assert after["completed_minutes"] == done_before + t["estimatedMinutes"]


@pytest.mark.asyncio
async def test_api_requires_sign_in():
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        assert (await anon.get("/api/v1/study-plan/today")).status_code == 401
