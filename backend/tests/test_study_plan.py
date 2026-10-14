"""
The study plan follows the learner model: it is rebuilt from the latest knowledge gaps and concept
mastery written by the adaptive quiz, and keeps tasks the learner has already completed.
"""
import uuid

import pytest

from backend.app.repositories.bkt import bkt_repo
from backend.app.repositories.workspaces import workspace_repo


async def _new_workspace() -> str:
    ws_id = f"ws_plan_{uuid.uuid4().hex[:8]}"
    await workspace_repo.create(workspace_id=ws_id, name="Operating Systems", goal="Learn OS", level="beginner")
    return ws_id


async def _plan(client, ws_id: str) -> dict:
    res = await client.get(f"/api/v1/workspaces/{ws_id}/study-plan")
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
async def test_plan_starts_with_starter_tasks_then_follows_quiz_gaps(async_client):
    ws_id = await _new_workspace()

    first = await _plan(async_client, ws_id)
    assert [t["tag"] for t in first["tasks"]] == ["Diagnostic", "Fundamentals"]

    # The adaptive quiz writes gaps and mastery under the workspace's learner id
    await bkt_repo.upsert_knowledge_gap(ws_id, "Memory", "Paging", 0.8, "critical_gap", {"low_accuracy": True})
    await bkt_repo.upsert_knowledge_gap(ws_id, "Memory", "TLB", 0.2, "strong", {})
    await bkt_repo.upsert_concept_mastery(ws_id, "Scheduling", "Round Robin", 0.65, True)

    second = await _plan(async_client, ws_id)
    titles = [t["title"] for t in second["tasks"]]
    assert titles == ["Review & Remediate: Paging", "Practice Problems: Round Robin"]
    assert second["tasks"][0]["priority"] == "high"
    assert second["tasks"][0]["scheduledFor"] == "today"


@pytest.mark.asyncio
async def test_completed_tasks_are_kept_when_the_plan_updates(async_client):
    ws_id = await _new_workspace()
    await bkt_repo.upsert_knowledge_gap(ws_id, "Memory", "Paging", 0.7, "needs_attention", {})

    plan = await _plan(async_client, ws_id)
    task_id = plan["tasks"][0]["id"]
    toggled = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/tasks/{task_id}/toggle")
    assert toggled.status_code == 200
    assert toggled.json()["today_completed_minutes"] == 25

    # A new gap appears after another quiz; the completed task and its minutes survive the rebuild
    await bkt_repo.upsert_knowledge_gap(ws_id, "Files", "Inodes", 0.9, "critical_gap", {})
    regenerated = await async_client.post(f"/api/v1/workspaces/{ws_id}/study-plan/generate")
    assert regenerated.status_code == 201
    body = regenerated.json()
    by_tag = {t["tag"]: t for t in body["tasks"]}
    assert by_tag["Paging"]["completed"] is True
    assert by_tag["Inodes"]["completed"] is False
    assert body["today_completed_minutes"] == 25
