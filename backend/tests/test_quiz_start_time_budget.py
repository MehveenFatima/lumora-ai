"""Starting a quiz never makes the browser wait past its limit: slow question writing continues in
the background and the page is told to retry (QUIZ_PREPARING)."""
import asyncio

import pytest

from backend.app.services import quiz_service as qs
from backend.app.services.question_generator import question_generator_service


@pytest.mark.asyncio
async def test_slow_question_writing_returns_preparing_quickly(async_client, monkeypatch):
    ws = (await async_client.post("/api/v1/workspaces", json={"name": "Slow quiz", "goal": "g", "level": "intermediate"})).json()

    async def concepts(workspace_id):
        return [{"concept": "Deadlock", "topic": "OS"}]

    finished = asyncio.Event()

    async def slow_pool(**kwargs):
        await asyncio.sleep(0.5)
        finished.set()
        return []

    monkeypatch.setattr(question_generator_service, "extract_available_concepts", concepts)
    monkeypatch.setattr(question_generator_service, "generate_candidate_pool", slow_pool)
    monkeypatch.setattr(qs, "QUIZ_START_BUDGET_SECONDS", 0.05)

    res = await async_client.post(f"/api/v1/workspaces/{ws['id']}/quizzes", json={"target_question_count": 5})
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "QUIZ_PREPARING"
    await asyncio.wait_for(finished.wait(), timeout=2)  # kept running in the background
