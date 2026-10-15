"""
Quiz candidate generation asks the AI provider about several concepts. Those requests are
independent, so they run concurrently and are bounded by a time budget; a slow provider must
never push quiz creation past the API timeout.
"""
import asyncio
import time
from types import SimpleNamespace

import pytest

from backend.app.ai.gateway import ai_gateway
from backend.app.services import question_generator as qg
from backend.app.services.question_generator import question_generator_service

CHUNKS = [
    {
        "id": f"chunk_{i}",
        "document_id": "doc_1",
        "document_name": "os-notes.pdf",
        "page_number": i + 1,
        "content": (
            f"Topic {i}: The operating system scheduler selects the next process using policy {i}. "
            "Round robin assigns each process a fixed time quantum and preempts it when the quantum expires. "
            "Paging divides memory into fixed-size frames and maps virtual pages through a page table."
        ),
    }
    for i in range(6)
]
CONCEPTS = ["Round Robin", "Paging", "Page Table", "Time Quantum", "Preemption", "Frames"]


@pytest.mark.asyncio
async def test_ai_candidate_requests_run_concurrently(monkeypatch):
    calls = []

    async def slow_provider(request):
        calls.append(request)
        await asyncio.sleep(0.4)
        return SimpleNamespace(structured_data={"questions": []})

    monkeypatch.setattr(ai_gateway, "generate_structured", slow_provider)

    start = time.perf_counter()
    candidates = await question_generator_service.generate_candidate_pool(
        "ws_concurrency", target_count=5, target_concepts=CONCEPTS, chunks=CHUNKS
    )
    elapsed = time.perf_counter() - start

    assert len(calls) == 6
    # Six sequential 0.4 s calls would take 2.4 s; concurrently they take about one call's time
    assert elapsed < 1.5
    assert isinstance(candidates, list)


@pytest.mark.asyncio
async def test_slow_provider_is_cut_off_by_the_time_budget(monkeypatch):
    async def stuck_provider(request):
        await asyncio.sleep(30)

    monkeypatch.setattr(ai_gateway, "generate_structured", stuck_provider)
    monkeypatch.setattr(qg, "AI_CANDIDATE_BUDGET_SECONDS", 0.3)

    start = time.perf_counter()
    candidates = await question_generator_service.generate_candidate_pool(
        "ws_budget", target_count=5, target_concepts=CONCEPTS, chunks=CHUNKS
    )

    assert time.perf_counter() - start < 3
    assert isinstance(candidates, list)
