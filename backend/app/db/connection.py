from typing import Optional, Any, List, Dict
import asyncio
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Global asyncpg connection pool if PostgreSQL is configured
_pool = None


async def get_db_pool():
    global _pool
    if _pool is not None:
        try:
            if hasattr(_pool, "_loop") and _pool._loop.is_closed():
                _pool = None
        except Exception:
            _pool = None

    if _pool is None and settings.database_url:
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=10,
                timeout=30.0,
            )
            logger.info("Connected to Supabase PostgreSQL database pool.")
        except Exception as e:
            logger.warning(
                f"Could not connect to database pool ({e}). Operating in memory-backed mode."
            )
            _pool = None
            if settings.presentation_mode:
                logger.error(f"Presentation backend unavailable: PostgreSQL connection error: {e}")
    return _pool


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
