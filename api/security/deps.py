from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.context import set_user_id
from api.core.errors import ApiError
from api.db import get_db
from api.db.models import PracticeSession, User
from api.security import CurrentUser
from api.security.tokens import verify_access_token


async def _load_user(db: AsyncSession, user_id: str) -> User:
    user = await session_get(db, User, user_id)
    if user is None:
        raise ApiError("auth_invalid_credentials")
    return user


async def session_get(db: AsyncSession, model, pk: str):
    return await db.get(model, pk)


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise ApiError("auth_token_expired")
    token = header.split(" ", 1)[1].strip()
    payload = verify_access_token(token)
    user = await _load_user(db, payload["sub"])

    principal = CurrentUser(
        user_id=user.id,
        email=user.email,
        name=user.name,
        learning_level=user.learning_level,
    )
    request.state.principal = principal
    request.state.user_id = user.id
    set_user_id(user.id)
    return principal


async def optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    if not request.headers.get("Authorization", "").lower().startswith("bearer "):
        return None
    try:
        return await require_auth(request, db)
    except ApiError:
        return None


async def require_session_owner(
    session_id: str,
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> PracticeSession:
    session = await db.get(PracticeSession, session_id)
    if session is None or session.user_id != principal.user_id:
        raise ApiError("session_not_found")
    return session
