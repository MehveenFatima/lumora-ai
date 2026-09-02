from typing import Optional, Any, List, Dict
import asyncio
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Global asyncpg connection pool if PostgreSQL is configured
_pool = None


async def get_db_pool():
    global _pool
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
    return _pool


async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Closed database connection pool.")
