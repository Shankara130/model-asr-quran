from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.core.ids import new_token_id, new_user_id
from api.db import get_db
from api.db.models import AuthRefreshToken, User, UserPreference
from api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    SignupRequest,
    Tokens,
    UserPublic,
)
from api.security import CurrentUser
from api.security.deps import require_auth
from api.security.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_TTL_DAYS = 30


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _create_refresh_row(session: AsyncSession, user_id: str) -> str:
    token = generate_refresh_token()
    now = datetime.now(timezone.utc)
    session.add(
        AuthRefreshToken(
            id=new_token_id(),
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            issued_at=_iso(now),
            expires_at=_iso(now + timedelta(days=REFRESH_TTL_DAYS)),
        )
    )
    await session.flush()
    return token


async def _issue_pair(session: AsyncSession, user_id: str) -> Tokens:
    refresh = await _create_refresh_row(session, user_id)
    await session.commit()
    return Tokens(
        access_token=issue_access_token(user_id),
        refresh_token=refresh,
        expires_in=3600,
    )


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        learning_level=user.learning_level,
        created_at=user.created_at,
    )


@router.post(
    "/signup", response_model=AuthResponse, status_code=201, summary="Register a new account"
)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Create a user and return access + refresh tokens.

    Dev stub: any password is accepted; emails must be unique
    (`auth_email_exists` 409 on conflict).
    """
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise ApiError("auth_email_exists")

    user = User(
        id=new_user_id(),
        name=body.name,
        email=body.email,
        password_hash="dev-stub",  # no bcrypt (dev stub)
        learning_level="beginner",
    )
    db.add(user)
    await db.flush()
    db.add(UserPreference(user_id=user.id))
    tokens = await _issue_pair(db, user.id)
    return AuthResponse(user=_user_public(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse, summary="Log in")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Exchange credentials for access + refresh tokens.

    Dev stub: any password is accepted; only the email must exist
    (`auth_invalid_credentials` otherwise).
    """
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise ApiError("auth_invalid_credentials")
    tokens = await _issue_pair(db, user.id)
    return AuthResponse(user=_user_public(user), tokens=tokens)


@router.get("/me", response_model=MeResponse, summary="Get the current user")
async def me(principal: CurrentUser = Depends(require_auth)) -> MeResponse:
    """Restore the authenticated user's session (validate the access token)."""
    return MeResponse(
        user=UserPublic(
            id=principal.user_id,
            name=principal.name,
            email=principal.email,
            learning_level=principal.learning_level,
        )
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Rotate the access token")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    """Exchange a valid refresh token for a new access + refresh pair (rotated).

    Returns `auth_refresh_failed` (401) if the token is unknown or revoked.
    """
    token_hash = hash_refresh_token(body.refresh_token)
    row = await db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash))
    if row is None or row.revoked_at is not None:
        raise ApiError("auth_refresh_failed")

    # Rotate: revoke old, issue new pair.
    row.revoked_at = _iso(datetime.now(timezone.utc))
    tokens = await _issue_pair(db, row.user_id)
    return RefreshResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=LogoutResponse, summary="Revoke the refresh token")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> LogoutResponse:
    """Revoke the supplied refresh token. The client should also clear local storage."""
    token_hash = hash_refresh_token(body.refresh_token)
    row = await db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash))
    if row is not None and row.revoked_at is None:
        row.revoked_at = _iso(datetime.now(timezone.utc))
        await db.commit()
    return LogoutResponse(success=True)
