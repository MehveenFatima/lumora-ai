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

    async def create(self, email: str, name: str, password_hash: str, email_verified: bool = True) -> Dict[str, Any]:
        email = self.normalize_email(email)
        now = datetime.now(timezone.utc)
        user = {
            "id": f"usr_{uuid.uuid4().hex}",
            "email": email,
            "name": name.strip(),
            "password_hash": password_hash,
            "email_verified": email_verified,
            "password_changed_at": None,
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
                        INSERT INTO users (id, email, name, password_hash, email_verified, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        user["id"], email, user["name"], password_hash, email_verified, now,
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

    async def _update(self, user_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates the given columns (names come from this module only, never from input)."""
        pool = await get_db_pool()
        if pool:
            assignments = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(fields))
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"UPDATE users SET {assignments} WHERE id = $1 RETURNING *", user_id, *fields.values()
                )
                return dict(row) if row else None
        user = _memory_users.get(user_id)
        if user:
            user.update(fields)
        return user

    async def mark_email_verified(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self._update(user_id, {"email_verified": True})

    async def update_password(self, user_id: str, password_hash: str) -> Optional[Dict[str, Any]]:
        # Sessions issued before this instant stop working (see deps.get_current_user)
        return await self._update(
            user_id, {"password_hash": password_hash, "password_changed_at": datetime.now(timezone.utc)}
        )

    async def update_name(self, user_id: str, name: str) -> Optional[Dict[str, Any]]:
        return await self._update(user_id, {"name": name.strip()})

    async def delete(self, user_id: str) -> None:
        """Deletes the account; workspaces and all learner data cascade with it."""
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM users WHERE id = $1", user_id)
            return
        _memory_users.pop(user_id, None)


user_repo = UserRepository()
