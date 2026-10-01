"""
Password hashing and session tokens.

Passwords are hashed with PBKDF2-HMAC-SHA256 (600,000 iterations, per-user random salt),
the same construction Django uses by default, so no native dependency is required.
Sessions are stateless HS256 JWTs carried in an httpOnly cookie (or a Bearer header).
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 600_000
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER = "lumora-api"

_ephemeral_secret: Optional[str] = None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGORITHM}${_PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != _PBKDF2_ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def get_jwt_secret() -> str:
    """
    Returns the signing secret. In production JWT_SECRET is mandatory (enforced at start-up).
    In development a random per-process secret is used if none is configured, which means
    sessions do not survive an API restart.
    """
    global _ephemeral_secret
    if settings.jwt_secret:
        return settings.jwt_secret
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET is not set; using an ephemeral development secret. "
            "Sessions will be invalidated when the API restarts."
        )
    return _ephemeral_secret


def create_session_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.session_ttl_hours),
        "iss": _JWT_ISSUER,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[str]:
    """Returns the user id for a valid, unexpired token, otherwise None."""
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[_JWT_ALGORITHM],
            issuer=_JWT_ISSUER,
            options={"require": ["sub", "exp", "iat"]},
        )
        return str(payload["sub"])
    except jwt.PyJWTError:
        return None
