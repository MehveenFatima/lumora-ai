"""
Target completion date: it can't be set in the past, the study plan counts down to it, and once
it has passed no plan is generated until the learner sets a new date.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.repositories.bkt import bkt_repo

TODAY = datetime.now(timezone.utc).date()


def _iso(d: date) -> str:
    return d.isoformat()


async def _create(client, **extra):
    body = {"name": "Computer Networks", "goal": "Semester exam", "level": "intermediate", **extra}
    return await client.post("/api/v1/workspaces", json=body)


@pytest.mark.asyncio
async def test_past_target_date_is_rejected_on_create(async_client):
    res = await _create(async_client, target_date=_iso(TODAY - timedelta(days=1)))
    assert res.status_code == 422
    assert "can't be in the past" in res.json()["detail"]


@pytest.mark.asyncio
async def test_today_and_future_dates_are_accepted(async_client):
    today = await _create(async_client, target_date=_iso(TODAY))
    assert today.status_code == 201 and today.json()["target_date"] == _iso(TODAY)
    later = await _create(async_client, target_date=_iso(TODAY + timedelta(days=60)))
    assert later.status_code == 201


@pytest.mark.asyncio
async def test_missing_date_defaults_to_thirty_days_and_bad_dates_fail(async_client):
    res = await _create(async_client)
    assert res.status_code == 201
    assert res.json()["target_date"] == _iso(TODAY + timedelta(days=30))
    bad = await _create(async_client, target_date="31-07-2026")
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_learners_local_date_is_used(async_client):
    # A learner whose local date is already tomorrow can't pick today's UTC date
    tomorrow = TODAY + timedelta(days=1)
    res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Ahead", "goal": "g", "target_date": _iso(TODAY)},
        headers={"X-Client-Date": _iso(tomorrow)},
    )
    assert res.status_code == 422
    # An implausible header (more than a day off) is ignored
    res = await async_client.post(
        "/api/v1/workspaces",
        json={"name": "Spoofed", "goal": "g", "target_date": _iso(TODAY)},
        headers={"X-Client-Date": _iso(TODAY + timedelta(days=40))},
    )
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_plan_counts_down_to_the_target(async_client):
    ws = (await _create(async_client, target_date=_iso(TODAY + timedelta(days=12)))).json()
    plan = (await async_client.get(f"/api/v1/workspaces/{ws['id']}/study-plan")).json()
    assert plan["target_passed"] is False
    assert plan["days_remaining"] == 12
    assert plan["target_date"] == _iso(TODAY + timedelta(days=12))
    assert len(plan["tasks"]) >= 1


@pytest.mark.asyncio
async def test_no_plan_after_the_target_date_until_it_is_moved(async_client):
    ws = (await _create(async_client, target_date=_iso(TODAY + timedelta(days=5)))).json()
    ws_id = ws["id"]
    await bkt_repo.upsert_knowledge_gap(ws_id, "Transport", "TCP", 0.8, "critical_gap", {})

    # Seen from 10 days later (simulated with the learner's date header via the service)
    from backend.app.services.secondary_service import secondary_service

    later = TODAY + timedelta(days=10)
    passed = await secondary_service.get_or_generate_study_plan(ws_id, today=later)
    assert passed["target_passed"] is True and passed["tasks"] == []
    assert passed["days_remaining"] == -5

    # The workspace's date can't be moved into the past either
    bad = await async_client.patch(f"/api/v1/workspaces/{ws_id}", json={"target_date": _iso(TODAY - timedelta(days=2))})
    assert bad.status_code == 422

    moved = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}", json={"target_date": _iso(TODAY + timedelta(days=20)), "daily_target_minutes": 60}
    )
    assert moved.status_code == 200
    assert moved.json()["target_date"] == _iso(TODAY + timedelta(days=20))
    assert moved.json()["daily_target_minutes"] == 60

    plan = (await async_client.get(f"/api/v1/workspaces/{ws_id}/study-plan")).json()
    assert plan["target_passed"] is False and plan["days_remaining"] == 20
    assert any("TCP" in t["title"] for t in plan["tasks"])


@pytest.mark.asyncio
async def test_tasks_cannot_be_ticked_after_the_target_date(async_client, monkeypatch):
    ws = (await _create(async_client, target_date=_iso(TODAY))).json()
    plan = (await async_client.get(f"/api/v1/workspaces/{ws['id']}/study-plan")).json()
    task_id = plan["tasks"][0]["id"]

    from backend.app.api.routes import study_plans

    monkeypatch.setattr(study_plans, "client_today", lambda request=None: TODAY + timedelta(days=1))
    res = await async_client.post(f"/api/v1/workspaces/{ws['id']}/study-plan/tasks/{task_id}/toggle")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_only_the_owner_can_change_the_target(async_client, anon_client):
    ws = (await _create(async_client, target_date=_iso(TODAY + timedelta(days=3)))).json()
    res = await anon_client.patch(f"/api/v1/workspaces/{ws['id']}", json={"target_date": _iso(TODAY + timedelta(days=9))})
    assert res.status_code == 401
