import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.app.core.logging import get_logger
from backend.app.db.connection import get_db_pool

logger = get_logger(__name__)

# In-memory fallback used when no database is configured (local development and tests)
_memory_users: Dict[str, Dict[str, Any]] = {}


class EmailAlreadyRegisteredError(Exception):
    pass


class UserRepository:
    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    async def create(self, email: str, name: str, password_hash: str) -> Dict[str, Any]:
        email = self.normalize_email(email)
        now = datetime.now(timezone.utc)
        user = {
            "id": f"usr_{uuid.uuid4().hex}",
            "email": email,
            "name": name.strip(),
            "password_hash": password_hash,
            "created_at": now,
            "last_login_at": None,
        }

        pool = await get_db_pool()
        if pool:
            import asyncpg

            async with pool.acquire() as conn:
                try:
                    await conn.execute(
                        """
                        INSERT INTO users (id, email, name, password_hash, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user["id"], email, user["name"], password_hash, now,
                    )
                except asyncpg.UniqueViolationError:
                    raise EmailAlreadyRegisteredError(email)
            return user

        if any(u["email"] == email for u in _memory_users.values()):
            raise EmailAlreadyRegisteredError(email)
        _memory_users[user["id"]] = user
        return user

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email = self.normalize_email(email)
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
                return dict(row) if row else None
        return next((u for u in _memory_users.values() if u["email"] == email), None)

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
                return dict(row) if row else None
        return _memory_users.get(user_id)

    async def touch_login(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        pool = await get_db_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE users SET last_login_at = $2 WHERE id = $1", user_id, now)
            except Exception as e:
                logger.warning(f"Could not record login time for {user_id}: {e}")
            return
        if user_id in _memory_users:
            _memory_users[user_id]["last_login_at"] = now


user_repo = UserRepository()
