"""
Fitting BKT parameters from answers: the grid search recovers the parameters that generated the
data, and the guards keep the defaults until there is enough evidence.
"""
import random

import pytest
import pytest_asyncio

from backend.app.services import bkt_fitting
from backend.app.services.bkt_fitting import BKTParams, fit, log_likelihood, should_adopt
from backend.app.services.bkt_mastery import DEFAULT_P_G, DEFAULT_P_L0, DEFAULT_P_S, DEFAULT_P_T, bkt_service


def simulate(params: BKTParams, learners: int, length: int, seed: int = 7):
    rng = random.Random(seed)
    sequences = []
    for _ in range(learners):
        known = rng.random() < params.p_l0
        seq = []
        for _ in range(length):
            p_correct = (1 - params.p_s) if known else params.p_g
            seq.append(rng.random() < p_correct)
            if not known and rng.random() < params.p_t:
                known = True
        sequences.append(seq)
    return sequences


@pytest_asyncio.fixture(autouse=True)
async def restore_defaults():
    yield
    bkt_fitting._apply(BKTParams(), "default")
    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM bkt_parameters WHERE scope = 'global'")


def test_likelihood_prefers_the_generating_parameters():
    truth = BKTParams(0.5, 0.2, 0.15, 0.08)
    data = simulate(truth, 150, 8)
    assert log_likelihood(data, truth) > log_likelihood(data, BKTParams(0.1, 0.02, 0.3, 0.3))


def test_grid_search_recovers_the_parameters():
    truth = BKTParams(0.6, 0.2, 0.1, 0.05)
    result = fit(simulate(truth, 400, 10))
    p = result["params"]
    assert abs(p.p_l0 - truth.p_l0) <= 0.1
    assert abs(p.p_t - truth.p_t) <= 0.1
    assert abs(p.p_g - truth.p_g) <= 0.1
    assert abs(p.p_s - truth.p_s) <= 0.06
    assert result["log_likelihood"] >= result["default_log_likelihood"]
    assert should_adopt(result)


def test_defaults_are_kept_with_too_little_data():
    result = fit(simulate(BKTParams(0.6, 0.2, 0.1, 0.05), 5, 4))
    assert not should_adopt(result)


@pytest.mark.asyncio
async def test_refit_applies_a_good_fit_to_the_live_model(monkeypatch):
    truth = BKTParams(0.6, 0.2, 0.1, 0.05)
    data = simulate(truth, 300, 10)

    async def fake_sequences():
        return data

    monkeypatch.setattr(bkt_fitting, "load_sequences", fake_sequences)
    result = await bkt_fitting.refit()
    assert result["adopted"] is True and result["improvement"] > 0
    assert bkt_service.p_l0 == result["params"]["p_l0"] != DEFAULT_P_L0
    assert bkt_fitting.current_model()["source"] == "fitted"


@pytest.mark.asyncio
async def test_refit_without_enough_answers_changes_nothing(monkeypatch):
    async def few():
        return [[True, False]] * 3

    monkeypatch.setattr(bkt_fitting, "load_sequences", few)
    result = await bkt_fitting.refit()
    assert result == {**result, "adopted": False, "reason": "not_enough_data"}
    assert (bkt_service.p_l0, bkt_service.p_t, bkt_service.p_g, bkt_service.p_s) == (
        DEFAULT_P_L0, DEFAULT_P_T, DEFAULT_P_G, DEFAULT_P_S,
    )


@pytest.mark.asyncio
async def test_learner_model_endpoint(async_client):
    body = (await async_client.get("/api/v1/learner-model")).json()
    assert body["source"] == "default" and body["params"]["p_l0"] == DEFAULT_P_L0
