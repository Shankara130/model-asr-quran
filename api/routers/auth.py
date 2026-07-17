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
from api.security.tokens import generate_refresh_token, hash_refresh_token, issue_access_token
from api.services.supabase_auth import SupabaseAuthClient, SupabaseSession, sync_supabase_user
from api.settings import settings, supabase_auth_enabled

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_TTL_DAYS = 30


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _iso(value.astimezone(timezone.utc))
    return str(value)


async def _create_refresh_row(session: AsyncSession, user_id: str) -> str:
    token = generate_refresh_token()
    now = datetime.now(timezone.utc)
    session.add(
        AuthRefreshToken(
            id=new_token_id(),
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=now + timedelta(days=REFRESH_TTL_DAYS),
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
        expires_in=settings.access_token_ttl_seconds,
    )


def _tokens_from_supabase(session: SupabaseSession) -> Tokens:
    return Tokens(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )


def _user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        learning_level=user.learning_level,
        created_at=_as_iso(user.created_at),
    )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=201,
    summary="Sign up",
)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Create a user and return access + refresh tokens."""
    if supabase_auth_enabled():
        session = await SupabaseAuthClient().sign_up(
            email=body.email,
            password=body.password,
            name=body.name,
        )
        user = await sync_supabase_user(db, session.user, requested_name=body.name)
        return AuthResponse(user=_user_public(user), tokens=_tokens_from_supabase(session))

    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise ApiError("auth_email_exists")

    user = User(
        id=new_user_id(),
        name=body.name,
        email=body.email,
        password_hash="dev-stub",
    )
    db.add(user)
    await db.flush()
    db.add(UserPreference(user_id=user.id))
    tokens = await _issue_pair(db, user.id)
    return AuthResponse(user=_user_public(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse, summary="Log in")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Exchange credentials for access + refresh tokens."""
    if supabase_auth_enabled():
        session = await SupabaseAuthClient().sign_in_with_password(
            email=body.email,
            password=body.password,
        )
        user = await sync_supabase_user(db, session.user)
        return AuthResponse(user=_user_public(user), tokens=_tokens_from_supabase(session))

    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise ApiError("auth_invalid_credentials")
    tokens = await _issue_pair(db, user.id)
    return AuthResponse(user=_user_public(user), tokens=tokens)


@router.get("/me", response_model=MeResponse, summary="Get current user")
async def me(principal: CurrentUser = Depends(require_auth)) -> MeResponse:
    """Restore the authenticated user's session."""
    return MeResponse(
        user=UserPublic(
            id=principal.user_id,
            name=principal.name,
            email=principal.email,
            learning_level=principal.learning_level,
        )
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Rotate access token")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    """Exchange a valid refresh token for a new access + refresh pair."""
    if supabase_auth_enabled():
        session = await SupabaseAuthClient().refresh(body.refresh_token)
        await sync_supabase_user(db, session.user)
        return RefreshResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
        )

    token_hash = hash_refresh_token(body.refresh_token)
    row = await db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash))
    if row is None or row.revoked_at is not None:
        raise ApiError("auth_refresh_failed")

    row.revoked_at = datetime.now(timezone.utc)
    tokens = await _issue_pair(db, row.user_id)
    return RefreshResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=LogoutResponse, summary="Revoke refresh token")
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)) -> LogoutResponse:
    """Revoke the supplied refresh token. The client should also clear local storage."""
    if supabase_auth_enabled():
        try:
            await SupabaseAuthClient().logout()
        except ApiError:
            pass
        return LogoutResponse(success=True)

    token_hash = hash_refresh_token(body.refresh_token)
    row = await db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return LogoutResponse(success=True)
