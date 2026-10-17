import re
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Deque, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from backend.app.api.deps import CurrentUser, get_current_user
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.core.security import create_session_token, hash_password, password_version, verify_password
from backend.app.repositories.auth_codes import CodeCooldownError, auth_code_repo
from backend.app.repositories.users import EmailAlreadyRegisteredError, user_repo
from backend.app.services.email_service import EmailDeliveryError, email_service
from backend.app.services.notification_service import notification_service

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MIN_PASSWORD_LENGTH = 8

# A precomputed hash used to keep login timing similar for unknown emails
_DUMMY_HASH = hash_password("lumora-timing-equalizer")


def _check_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


def _check_password(v: str) -> str:
    if len(v) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain at least one letter and one number.")
    return v


def _check_code(v: str) -> str:
    v = (v or "").strip()
    if not re.fullmatch(r"\d{6}", v):
        raise ValueError("Enter the 6-digit code from the email.")
    return v


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)

    _email = field_validator("email")(classmethod(lambda cls, v: _check_email(v)))
    _password = field_validator("password")(classmethod(lambda cls, v: _check_password(v)))


class EmailRequest(BaseModel):
    email: str = Field(max_length=254)

    _email = field_validator("email")(classmethod(lambda cls, v: _check_email(v)))


class VerifyEmailRequest(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(max_length=12)

    _email = field_validator("email")(classmethod(lambda cls, v: _check_email(v)))
    _code = field_validator("code")(classmethod(lambda cls, v: _check_code(v)))


class ResetPasswordRequest(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(max_length=12)
    new_password: str = Field(max_length=256)

    _email = field_validator("email")(classmethod(lambda cls, v: _check_email(v)))
    _code = field_validator("code")(classmethod(lambda cls, v: _check_code(v)))
    _password = field_validator("new_password")(classmethod(lambda cls, v: _check_password(v)))


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)

    _password = field_validator("new_password")(classmethod(lambda cls, v: _check_password(v)))


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=256)


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


class RegisterResponse(BaseModel):
    verification_required: bool
    email: str
    email_sent: bool = False
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    token_type: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class AuthConfigResponse(BaseModel):
    email_verification_required: bool
    password_reset_available: bool


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
code_request_limiter = _RateLimiter(max_attempts=10, window_seconds=60 * 60)
code_verify_limiter = _RateLimiter(max_attempts=20, window_seconds=15 * 60)

_GENERIC_RESET_MESSAGE = "If an account exists for that email, we've sent a 6-digit reset code. It expires in {m} minutes."
_INVALID_CODE_MESSAGE = "That code is incorrect or has expired. Request a new code and try again."


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _send_code(user: CurrentUser, purpose: str) -> bool:
    """Issues and emails a code. Returns False if it could not be sent (the code is withdrawn)."""
    try:
        code = await auth_code_repo.issue(user["id"], purpose)
    except CodeCooldownError:
        return True  # a recent code is still valid; don't send another
    try:
        await email_service.send_code(user["email"], user.get("name"), code, purpose)
        return True
    except EmailDeliveryError as e:
        logger.error(f"Could not send {purpose} email for user {user['id']}: {e}")
        await auth_code_repo.withdraw(user["id"], purpose)
        return False


def _to_user_response(user: CurrentUser) -> UserResponse:
    return UserResponse(id=user["id"], email=user["email"], name=user["name"], created_at=user.get("created_at"))


def _start_session(response: Response, user: CurrentUser) -> AuthResponse:
    token = create_session_token(user["id"], password_version(user.get("password_changed_at")))
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


@router.get("/config", response_model=AuthConfigResponse)
async def auth_config() -> AuthConfigResponse:
    """Tells the sign-in pages which email features are switched on."""
    return AuthConfigResponse(
        email_verification_required=settings.email_verification_required,
        password_reset_available=settings.email_enabled,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response) -> RegisterResponse:
    if not settings.allow_registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is currently closed.")
    register_limiter.check(_client_ip(request))
    needs_verification = settings.email_verification_required
    try:
        user = await user_repo.create(
            email=payload.email,
            name=payload.name,
            password_hash=hash_password(payload.password),
            email_verified=not needs_verification,
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    logger.info(f"New account registered: {user['id']}")

    if needs_verification:
        sent = await _send_code(user, "verify_email")
        return RegisterResponse(verification_required=True, email=user["email"], email_sent=sent)

    await notification_service.welcome(user)
    session = _start_session(response, user)
    return RegisterResponse(
        verification_required=False,
        email=user["email"],
        user=session.user,
        access_token=session.access_token,
        token_type=session.token_type,
    )


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(payload: VerifyEmailRequest, request: Request, response: Response) -> AuthResponse:
    code_verify_limiter.check(f"{_client_ip(request)}|{payload.email}")
    user = await user_repo.get_by_email(payload.email)
    if not user or not await auth_code_repo.verify(user["id"], "verify_email", payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_CODE_MESSAGE)
    user = await user_repo.mark_email_verified(user["id"]) or user
    logger.info(f"Email verified for user {user['id']}")
    await notification_service.welcome(user)
    return _start_session(response, user)


@router.post("/resend-verification", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(payload: EmailRequest, request: Request) -> MessageResponse:
    code_request_limiter.check(f"{_client_ip(request)}|verify")
    if not settings.email_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Email is not configured on this server.")
    user = await user_repo.get_by_email(payload.email)
    if user and user.get("email_verified") is False:
        if not await _send_code(user, "verify_email"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="We couldn't send the email right now. Please try again in a few minutes.",
            )
    return MessageResponse(message="If this email is waiting for verification, a new code has been sent.")


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: EmailRequest, request: Request, background: BackgroundTasks) -> MessageResponse:
    code_request_limiter.check(f"{_client_ip(request)}|reset")
    if not settings.email_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset by email isn't available on this server yet.",
        )
    user = await user_repo.get_by_email(payload.email)
    if user:
        # Sent after the response so the reply takes the same time whether or not the account exists
        background.add_task(_send_code, user, "reset_password")
    return MessageResponse(message=_GENERIC_RESET_MESSAGE.format(m=settings.email_code_ttl_minutes))


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(payload: ResetPasswordRequest, request: Request, response: Response) -> AuthResponse:
    code_verify_limiter.check(f"{_client_ip(request)}|{payload.email}")
    user = await user_repo.get_by_email(payload.email)
    if not user or not await auth_code_repo.verify(user["id"], "reset_password", payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_CODE_MESSAGE)
    user = await user_repo.update_password(user["id"], hash_password(payload.new_password)) or user
    # Receiving the code proves the person controls this inbox
    user = await user_repo.mark_email_verified(user["id"]) or user
    login_limiter.reset(f"{_client_ip(request)}|{payload.email}")
    logger.info(f"Password reset for user {user['id']}")
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
    if user.get("email_verified") is False:
        if settings.email_enabled:
            await _send_code(user, "verify_email")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "EMAIL_NOT_VERIFIED",
                    "message": "Please verify your email first. We've sent a 6-digit code to your inbox.",
                    "email": user["email"],
                },
            )
        # Email was switched off after this account signed up; let them in rather than lock them out
        user = await user_repo.mark_email_verified(user["id"]) or user
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


@router.patch("/me", response_model=UserResponse)
async def update_profile(payload: UpdateProfileRequest, user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter your full name.")
    updated = await user_repo.update_name(user["id"], name) or user
    return _to_user_response(updated)


@router.post("/change-password", response_model=AuthResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
) -> AuthResponse:
    login_limiter.check(f"{_client_ip(request)}|{user['email']}")
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your current password is incorrect.")
    if verify_password(payload.new_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a password you haven't used here before.")
    updated = await user_repo.update_password(user["id"], hash_password(payload.new_password)) or user
    # Every other session is signed out; this browser gets a fresh one
    return _start_session(response, updated)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    login_limiter.check(f"{_client_ip(request)}|{user['email']}")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your password is incorrect.")

    from backend.app.repositories.chunks import chunk_repo
    from backend.app.repositories.documents import document_repo
    from backend.app.repositories.workspaces import workspace_repo
    from backend.app.services.storage import storage_service

    for ws in await workspace_repo.list_by_owner(user["id"]):
        for doc in await document_repo.list_by_workspace(ws["id"]):
            await chunk_repo.delete_by_document(doc["id"])
            await document_repo.delete(doc["id"])
            await storage_service.delete_file(doc.get("storage_path"))
        await workspace_repo.delete(ws["id"])
    await user_repo.delete(user["id"])
    logger.info(f"Account deleted: {user['id']}")
    return await logout(response)

