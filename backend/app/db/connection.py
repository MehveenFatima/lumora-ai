from typing import Optional, Any, List, Dict
import asyncio
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Global asyncpg connection pool if PostgreSQL is configured
_pool = None
_last_failure: float = 0.0
# After a failed connection attempt, wait this long before trying again (keeps requests fast)
RECONNECT_BACKOFF_SECONDS = 5.0


async def get_db_pool():
    global _pool, _last_failure
    if _pool is not None:
        try:
            if hasattr(_pool, "_loop") and _pool._loop.is_closed():
                _pool = None
        except Exception:
            _pool = None

    if _pool is None and settings.database_url:
        import time

        if time.monotonic() - _last_failure < RECONNECT_BACKOFF_SECONDS:
            return _require_pool_in_production()
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=5,
                timeout=30.0,
            )
            logger.info("Connected to Supabase PostgreSQL database pool.")
        except Exception as e:
            _last_failure = time.monotonic()
            _pool = None
            if settings.is_production:
                logger.error(f"Database unavailable ({type(e).__name__}); requests will get 503 until it recovers.")
                return _require_pool_in_production()
            logger.warning(
                f"Could not connect to database pool ({e}). Operating in memory-backed mode."
            )
            if settings.presentation_mode:
                logger.error(f"Presentation backend unavailable: PostgreSQL connection error: {e}")
    return _pool


def _require_pool_in_production():
    """
    In production a configured database must never be silently replaced by the in-memory store
    (accounts and uploads would vanish on restart), so requests fail with 503 instead.
    """
    if settings.is_production and settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable. Please try again in a moment.",
        )
    return None


async def connect_with_retry(attempts: int = 6) -> bool:
    """Start-up connection with exponential backoff (1, 2, 4, 8, 16 s) for databases that start slowly."""
    global _last_failure
    if not settings.database_url:
        return False
    for attempt in range(1, attempts + 1):
        _last_failure = 0.0
        try:
            if await get_db_pool():
                return True
        except HTTPException:
            pass
        if attempt < attempts:
            delay = 2 ** (attempt - 1)
            logger.warning(f"Database not reachable yet (attempt {attempt}/{attempts}); retrying in {delay}s.")
            await asyncio.sleep(delay)
    logger.error("Could not connect to the database after retries.")
    return False


def check_presentation_mode_database_availability(pool):
    """Enforces strict database availability in presentation mode."""
    if settings.presentation_mode and not pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Presentation backend unavailable: Real PostgreSQL database connection required in PRESENTATION_MODE. Please verify DATABASE_URL in environment.",
        )


async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Closed database connection pool.")
