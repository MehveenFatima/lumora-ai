import re
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from backend.app.api.deps import CurrentUser, get_current_user
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.core.security import create_session_token, hash_password, verify_password
from backend.app.repositories.users import EmailAlreadyRegisteredError, user_repo

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MIN_PASSWORD_LENGTH = 8

# A precomputed hash used to keep login timing similar for unknown emails
_DUMMY_HASH = hash_password("lumora-timing-equalizer")


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < _MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one number.")
        return v


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: Optional[datetime] = None


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


class _RateLimiter:
    """Small in-process sliding-window limiter for authentication endpoints."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_attempts:
            retry_after = int(self.window_seconds - (now - hits[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a few minutes and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_limiter = _RateLimiter(max_attempts=10, window_seconds=15 * 60)
register_limiter = _RateLimiter(max_attempts=10, window_seconds=60 * 60)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _to_user_response(user: CurrentUser) -> UserResponse:
    return UserResponse(id=user["id"], email=user["email"], name=user["name"], created_at=user.get("created_at"))


def _start_session(response: Response, user: CurrentUser) -> AuthResponse:
    token = create_session_token(user["id"])
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.effective_cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthResponse(user=_to_user_response(user), access_token=token)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response) -> AuthResponse:
    if not settings.allow_registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is currently closed.")
    register_limiter.check(_client_ip(request))
    try:
        user = await user_repo.create(
            email=payload.email,
            name=payload.name,
            password_hash=hash_password(payload.password),
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    logger.info(f"New account registered: {user['id']}")
    return _start_session(response, user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    email = payload.email.strip().lower()
    limiter_key = f"{_client_ip(request)}|{email}"
    login_limiter.check(limiter_key)

    user = await user_repo.get_by_email(email)
    password_ok = verify_password(payload.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")

    login_limiter.reset(limiter_key)
    await user_repo.touch_login(user["id"])
    return _start_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.effective_cookie_secure,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(user)
