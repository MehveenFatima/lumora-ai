from typing import Optional, Any, List, Dict
import asyncio
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Global asyncpg connection pool if PostgreSQL is configured
_pool = None
_last_failure: float = 0.0
# Short, secret-free reason for the last failed connection (shown by the health check)
_last_error: Optional[str] = None
# Result of applying migrations once the database was reached: None (not yet), "ok" or an error name
_migration_state: Optional[str] = None
# After a failed connection attempt, wait this long before trying again (keeps requests fast)
RECONNECT_BACKOFF_SECONDS = 5.0


async def get_db_pool():
    global _pool, _last_failure, _last_error
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
            _last_error = None
            logger.info("Connected to Supabase PostgreSQL database pool.")
        except Exception as e:
            from backend.app.db.migrations_runner import describe_db_error

            _last_failure = time.monotonic()
            _last_error = describe_db_error(e)
            _pool = None
            if settings.is_production:
                logger.error(f"Database unavailable ({_last_error}); requests will get 503 until it recovers.")
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


def database_state() -> Dict[str, Any]:
    """What the health check reports about the database, without touching it."""
    return {"last_error": _last_error, "migrations": _migration_state}


async def run_migrations() -> bool:
    """Applies pending migrations through the pool. A failure is logged and the API keeps serving."""
    global _migration_state
    pool = _pool
    if pool is None:
        return False
    from backend.app.db.migrations_runner import apply_migrations

    try:
        async with pool.acquire() as conn:
            total, done = await apply_migrations(conn)
        _migration_state = "ok"
        if done:
            logger.info(f"Applied migrations: {', '.join(done)}")
        logger.info(f"Database schema is up to date ({total} migrations).")
        return True
    except Exception as e:
        _migration_state = type(e).__name__
        logger.error(f"Could not apply database migrations ({type(e).__name__}: {e}).", exc_info=True)
        return False


async def keep_connecting(on_connect, interval: float = 30.0) -> None:
    """
    Background task started when the database was unreachable at start-up (for example a paused
    free-tier project): keeps trying, and runs `on_connect` once it is reachable again.
    """
    global _last_failure
    while True:
        await asyncio.sleep(interval)
        _last_failure = 0.0
        try:
            if await get_db_pool():
                logger.info("Database reachable again.")
                await on_connect()
                return
        except HTTPException:
            pass
        except Exception as e:  # never let the retry loop die
            logger.warning(f"Database retry failed: {type(e).__name__}")


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
