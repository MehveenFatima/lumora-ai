"""
Fitting the BKT parameters from learners' real quiz answers.

LumoraAI starts with the textbook BKT values (P(L0)=0.30, P(T)=0.15, P(G)=0.20, P(S)=0.10).
Once enough answers have been collected, this module fits the four values that best explain them:
for every concept a learner practised, the ordered right/wrong answers form one sequence, and a
brute-force grid search (as in pyBKT's brute-force mode) picks the parameters with the highest
log-likelihood under the BKT forward algorithm, evaluated for all grid points at once with numpy.

Guards keep the model sensible:
- nothing changes until there are at least MIN_ATTEMPTS answers in MIN_SEQUENCES sequences;
- guess and slip are capped at 0.30 (above that BKT can explain answers "backwards");
- the fitted values are used only if they explain the data clearly better than the defaults.

The fitted values are stored in `bkt_parameters` and applied to the live BKT service; they are
refitted once a day (see `refit_loop`) and can be refitted by hand with
`python -m backend.app.cli fit-bkt`.
"""
from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from backend.app.core.logging import get_logger
from backend.app.services.bkt_mastery import (
    DEFAULT_P_G,
    DEFAULT_P_L0,
    DEFAULT_P_S,
    DEFAULT_P_T,
    bkt_service,
)

logger = get_logger(__name__)

MIN_ATTEMPTS = 200
MIN_SEQUENCES = 20
# Log-likelihood the fit must gain over the defaults before it is used (a likelihood-ratio
# margin, so small noisy samples don't move the model)
MIN_IMPROVEMENT = 3.0
REFIT_EVERY_SECONDS = 24 * 3600

GRID_L0 = np.round(np.arange(0.05, 0.91, 0.05), 2)
GRID_T = np.array([0.02, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5])
GRID_G = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.3])
GRID_S = np.array([0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3])
_EPS = 1e-9


@dataclass
class BKTParams:
    p_l0: float = DEFAULT_P_L0
    p_t: float = DEFAULT_P_T
    p_g: float = DEFAULT_P_G
    p_s: float = DEFAULT_P_S

    def as_dict(self) -> Dict[str, float]:
        return {"p_l0": self.p_l0, "p_t": self.p_t, "p_g": self.p_g, "p_s": self.p_s}


def log_likelihood(sequences: Sequence[Sequence[bool]], params: BKTParams) -> float:
    """Total log-likelihood of the answer sequences under one parameter set."""
    return float(_grid_log_likelihood(
        sequences,
        np.array([params.p_l0]), np.array([params.p_t]), np.array([params.p_g]), np.array([params.p_s]),
    )[0])


def _grid_log_likelihood(sequences, l0, t, g, s) -> np.ndarray:
    """Log-likelihood for many parameter sets at once (arrays of equal length)."""
    total = np.zeros_like(l0, dtype=float)
    for seq in sequences:
        p = l0.astype(float).copy()
        for correct in seq:
            p_correct = p * (1 - s) + (1 - p) * g
            if correct:
                total += np.log(np.clip(p_correct, _EPS, 1.0))
                posterior = p * (1 - s) / np.clip(p_correct, _EPS, None)
            else:
                p_wrong = 1 - p_correct
                total += np.log(np.clip(p_wrong, _EPS, 1.0))
                posterior = p * s / np.clip(p_wrong, _EPS, None)
            p = posterior + (1 - posterior) * t
    return total


def fit(sequences: Sequence[Sequence[bool]]) -> Dict[str, Any]:
    """Grid-search fit. Returns the best parameters, their log-likelihood and the defaults'."""
    combos = np.array(list(itertools.product(GRID_L0, GRID_T, GRID_G, GRID_S)))
    ll = _grid_log_likelihood(sequences, combos[:, 0], combos[:, 1], combos[:, 2], combos[:, 3])
    best = int(np.argmax(ll))
    l0, t, g, s = (round(float(x), 4) for x in combos[best])
    return {
        "params": BKTParams(l0, t, g, s),
        "log_likelihood": float(ll[best]),
        "default_log_likelihood": log_likelihood(sequences, BKTParams()),
        "attempts": int(sum(len(x) for x in sequences)),
        "sequences": len(sequences),
    }


def should_adopt(result: Dict[str, Any]) -> bool:
    return (
        result["attempts"] >= MIN_ATTEMPTS
        and result["sequences"] >= MIN_SEQUENCES
        and result["log_likelihood"] - result["default_log_likelihood"] >= MIN_IMPROVEMENT
    )


# --------------------------------------------------------------------------------------------
# Data, storage and the live model
# --------------------------------------------------------------------------------------------

async def load_sequences() -> List[List[bool]]:
    """Every (learner, workspace, concept) answer sequence, in the order the answers were given."""
    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.workspace_id, a.user_id, lower(q.concept) AS concept, a.is_correct
            FROM quiz_attempts a
            JOIN quiz_questions q ON q.id = a.question_id
            ORDER BY a.workspace_id, a.user_id, lower(q.concept), a.answered_at, a.created_at
            """
        )
    sequences: Dict[tuple, List[bool]] = {}
    for r in rows:
        sequences.setdefault((r["workspace_id"], r["user_id"], r["concept"]), []).append(bool(r["is_correct"]))
    return list(sequences.values())


_state: Dict[str, Any] = {"source": "default", "params": BKTParams().as_dict()}


def current_model() -> Dict[str, Any]:
    """The parameters in use and where they came from (for the analytics page and health check)."""
    return dict(_state)


def _apply(params: BKTParams, source: str, info: Optional[Dict[str, Any]] = None) -> None:
    bkt_service.p_l0, bkt_service.p_t, bkt_service.p_g, bkt_service.p_s = (
        params.p_l0, params.p_t, params.p_g, params.p_s,
    )
    _state.clear()
    _state.update({"source": source, "params": params.as_dict(), **(info or {})})


async def load_saved() -> None:
    """Applies the stored fit, if there is one (called when the database connects)."""
    from backend.app.db.connection import get_db_pool

    pool = await get_db_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bkt_parameters WHERE scope = 'global'")
    if row and row["adopted"]:
        _apply(
            BKTParams(row["p_l0"], row["p_t"], row["p_g"], row["p_s"]),
            "fitted",
            {"attempts": row["attempts"], "sequences": row["sequences"], "fitted_at": row["fitted_at"].isoformat()},
        )


async def refit() -> Dict[str, Any]:
    """Fits from all answers, stores the result and applies it if it passes the guards."""
    from backend.app.db.connection import get_db_pool

    sequences = await load_sequences()
    attempts = sum(len(s) for s in sequences)
    if attempts < MIN_ATTEMPTS or len(sequences) < MIN_SEQUENCES:
        return {"adopted": False, "reason": "not_enough_data", "attempts": attempts, "sequences": len(sequences),
                "needed_attempts": MIN_ATTEMPTS, "needed_sequences": MIN_SEQUENCES}

    result = await asyncio.to_thread(fit, sequences)
    adopted = should_adopt(result)
    p = result["params"]
    now = datetime.now(timezone.utc)
    pool = await get_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bkt_parameters (scope, p_l0, p_t, p_g, p_s, attempts, sequences,
                                            log_likelihood, default_log_likelihood, adopted, fitted_at)
                VALUES ('global', $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (scope) DO UPDATE SET
                    p_l0 = EXCLUDED.p_l0, p_t = EXCLUDED.p_t, p_g = EXCLUDED.p_g, p_s = EXCLUDED.p_s,
                    attempts = EXCLUDED.attempts, sequences = EXCLUDED.sequences,
                    log_likelihood = EXCLUDED.log_likelihood,
                    default_log_likelihood = EXCLUDED.default_log_likelihood,
                    adopted = EXCLUDED.adopted, fitted_at = EXCLUDED.fitted_at
                """,
                p.p_l0, p.p_t, p.p_g, p.p_s, result["attempts"], result["sequences"],
                result["log_likelihood"], result["default_log_likelihood"], adopted, now,
            )
    if adopted:
        _apply(p, "fitted", {"attempts": result["attempts"], "sequences": result["sequences"], "fitted_at": now.isoformat()})
    logger.info(
        f"BKT fit on {result['attempts']} answers / {result['sequences']} sequences: {p.as_dict()} "
        f"(log-likelihood {result['log_likelihood']:.1f} vs default {result['default_log_likelihood']:.1f}; "
        f"{'adopted' if adopted else 'kept defaults'})"
    )
    return {
        "adopted": adopted,
        "params": p.as_dict(),
        "attempts": result["attempts"],
        "sequences": result["sequences"],
        "log_likelihood": round(result["log_likelihood"], 2),
        "default_log_likelihood": round(result["default_log_likelihood"], 2),
        "improvement": round(result["log_likelihood"] - result["default_log_likelihood"], 2),
    }


async def refit_loop(first_delay_seconds: int = 120) -> None:
    """Refits once a day for the life of the API."""
    await asyncio.sleep(first_delay_seconds)
    while True:
        try:
            await refit()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"BKT refit failed: {e}")
        await asyncio.sleep(REFIT_EVERY_SECONDS)
