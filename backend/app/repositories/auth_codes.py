"""
One-time email codes (verification and password reset).

Only an HMAC of each code is stored, keyed with the server secret, so a database leak does not
reveal usable codes. A code is single-use, expires, and is locked after too many wrong guesses.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.core.security import get_jwt_secret
from backend.app.db.connection import get_db_pool

MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MAX_CODES_PER_HOUR = 5

_memory_codes: List[Dict[str, Any]] = []


class CodeCooldownError(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Please wait {retry_after}s before requesting another code.")
        self.retry_after = retry_after


def _hash_code(user_id: str, purpose: str, code: str) -> str:
    key = get_jwt_secret().encode("utf-8")
    return hmac.new(key, f"{user_id}:{purpose}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class AuthCodeRepository:
    async def _recent(self, user_id: str, purpose: str, since: datetime) -> List[Dict[str, Any]]:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM email_codes WHERE user_id = $1 AND purpose = $2 AND created_at >= $3 "
                    "ORDER BY created_at DESC",
                    user_id, purpose, since,
                )
                return [dict(r) for r in rows]
        return sorted(
            (c for c in _memory_codes if c["user_id"] == user_id and c["purpose"] == purpose and c["created_at"] >= since),
            key=lambda c: c["created_at"],
            reverse=True,
        )

    async def issue(self, user_id: str, purpose: str) -> str:
        """Creates a new code (invalidating older ones). Raises CodeCooldownError when asked too often."""
        now = datetime.now(timezone.utc)
        recent = await self._recent(user_id, purpose, now - timedelta(hours=1))
        if recent:
            age = (now - recent[0]["created_at"]).total_seconds()
            if age < RESEND_COOLDOWN_SECONDS:
                raise CodeCooldownError(int(RESEND_COOLDOWN_SECONDS - age) + 1)
            if len(recent) >= MAX_CODES_PER_HOUR:
                oldest = recent[-1]["created_at"]
                raise CodeCooldownError(int(3600 - (now - oldest).total_seconds()) + 1)

        code = generate_code()
        record = {
            "id": f"code_{uuid.uuid4().hex}",
            "user_id": user_id,
            "purpose": purpose,
            "code_hash": _hash_code(user_id, purpose, code),
            "attempts": 0,
            "expires_at": now + timedelta(minutes=settings.email_code_ttl_minutes),
            "consumed_at": None,
            "created_at": now,
        }
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Only the newest code is valid
                    await conn.execute(
                        "UPDATE email_codes SET consumed_at = $3 WHERE user_id = $1 AND purpose = $2 AND consumed_at IS NULL",
                        user_id, purpose, now,
                    )
                    await conn.execute(
                        "INSERT INTO email_codes (id, user_id, purpose, code_hash, attempts, expires_at, created_at) "
                        "VALUES ($1, $2, $3, $4, 0, $5, $6)",
                        record["id"], user_id, purpose, record["code_hash"], record["expires_at"], now,
                    )
        else:
            for c in _memory_codes:
                if c["user_id"] == user_id and c["purpose"] == purpose and c["consumed_at"] is None:
                    c["consumed_at"] = now
            _memory_codes.append(record)
        return code

    async def withdraw(self, user_id: str, purpose: str) -> None:
        """Removes the newest unused code (used when the email could not be sent)."""
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM email_codes WHERE id = (SELECT id FROM email_codes WHERE user_id = $1 AND purpose = $2 "
                    "AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1)",
                    user_id, purpose,
                )
            return
        active = [c for c in _memory_codes if c["user_id"] == user_id and c["purpose"] == purpose and c["consumed_at"] is None]
        if active:
            _memory_codes.remove(max(active, key=lambda c: c["created_at"]))

    async def verify(self, user_id: str, purpose: str, code: str) -> bool:
        """Checks a submitted code; consumes it on success and counts the attempt on failure."""
        code = (code or "").strip()
        now = datetime.now(timezone.utc)
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        "SELECT * FROM email_codes WHERE user_id = $1 AND purpose = $2 AND consumed_at IS NULL "
                        "ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
                        user_id, purpose,
                    )
                    if not row or row["expires_at"] <= now or row["attempts"] >= MAX_ATTEMPTS:
                        return False
                    if hmac.compare_digest(row["code_hash"], _hash_code(user_id, purpose, code)):
                        await conn.execute("UPDATE email_codes SET consumed_at = $2 WHERE id = $1", row["id"], now)
                        return True
                    await conn.execute("UPDATE email_codes SET attempts = attempts + 1 WHERE id = $1", row["id"])
                    return False

        active = [c for c in _memory_codes if c["user_id"] == user_id and c["purpose"] == purpose and c["consumed_at"] is None]
        if not active:
            return False
        rec = max(active, key=lambda c: c["created_at"])
        if rec["expires_at"] <= now or rec["attempts"] >= MAX_ATTEMPTS:
            return False
        if hmac.compare_digest(rec["code_hash"], _hash_code(user_id, purpose, code)):
            rec["consumed_at"] = now
            return True
        rec["attempts"] += 1
        return False


auth_code_repo = AuthCodeRepository()
