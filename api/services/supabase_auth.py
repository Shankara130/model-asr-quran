from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.db.models import User, UserPreference
from api.settings import settings, supabase_auth_enabled


@dataclass(frozen=True)
class SupabaseSession:
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict[str, Any]


class SupabaseAuthClient:
    """Thin async wrapper around Supabase Auth REST endpoints."""

    def __init__(self) -> None:
        if not supabase_auth_enabled():
            raise RuntimeError("Supabase auth is not configured")
        self.base_url = settings.supabase_url.rstrip("/")  # type: ignore[union-attr]
        self.anon_key = settings.supabase_anon_key  # type: ignore[assignment]
        self.admin_key = settings.supabase_service_role_key or self.anon_key

    def _headers(self, bearer: str | None = None, *, admin: bool = False) -> dict[str, str]:
        key = self.admin_key if admin else self.anon_key
        headers = {"apikey": key, "Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    async def sign_up(self, *, email: str, password: str, name: str) -> SupabaseSession:
        payload = {"email": email, "password": password, "data": {"name": name}}
        data = await self._post("/auth/v1/signup", payload)
        return self._session_from_payload(data)

    async def sign_in_with_password(self, *, email: str, password: str) -> SupabaseSession:
        payload = {"email": email, "password": password}
        data = await self._post("/auth/v1/token?grant_type=password", payload)
        return self._session_from_payload(data)

    async def refresh(self, refresh_token: str) -> SupabaseSession:
        data = await self._post(
            "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": refresh_token},
        )
        return self._session_from_payload(data)

    async def logout(self, access_token: str | None = None) -> None:
        headers = self._headers(access_token, admin=access_token is None)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.base_url}/auth/v1/logout", headers=headers)
        if response.status_code not in {200, 204}:
            raise ApiError("auth_refresh_failed")

    async def get_user(self, access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.base_url}/auth/v1/user",
                headers=self._headers(access_token),
            )
        if response.status_code == 401:
            raise ApiError("auth_token_expired")
        if response.status_code >= 400:
            raise ApiError("auth_invalid_credentials")
        data = response.json()
        return data.get("user") or data

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=payload,
            )
        if response.status_code == 400 and "already" in response.text.lower():
            raise ApiError("auth_email_exists")
        if response.status_code in {400, 401, 422}:
            raise ApiError("auth_invalid_credentials")
        if response.status_code >= 400:
            raise ApiError("internal_error", details={"supabaseStatus": response.status_code})
        return response.json()

    def _session_from_payload(self, data: dict[str, Any]) -> SupabaseSession:
        user = data.get("user") or {}
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        if not access_token or not refresh_token or not user.get("id"):
            raise ApiError("auth_invalid_credentials")
        return SupabaseSession(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(data.get("expires_in") or settings.access_token_ttl_seconds),
            user=user,
        )


def user_name_from_supabase(user: dict[str, Any], fallback_email: str = "") -> str:
    metadata = user.get("user_metadata") or {}
    name = metadata.get("name") or metadata.get("full_name") or user.get("name")
    if name:
        return str(name)
    email = str(user.get("email") or fallback_email)
    return email.split("@", 1)[0] if email else "Sobat Ngaji"


async def sync_supabase_user(
    db: AsyncSession,
    user: dict[str, Any],
    *,
    requested_name: str | None = None,
) -> User:
    try:
        user_id = str(UUID(str(user["id"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError("auth_invalid_credentials") from exc
    email = str(user.get("email") or "").strip()
    if not email:
        raise ApiError("auth_invalid_credentials")
    row = await db.get(User, user_id)
    if row is None and email:
        row = await db.scalar(select(User).where(User.email == email))
        if row is not None and row.id != user_id:
            raise ApiError("auth_identity_conflict")
    if row is None:
        row = User(
            id=user_id,
            name=requested_name or user_name_from_supabase(user, email),
            email=email,
            password_hash="supabase",
            avatar_url=(user.get("user_metadata") or {}).get("avatar_url"),
            learning_level="beginner",
        )
        db.add(row)
        await db.flush()
        db.add(UserPreference(user_id=row.id))
    else:
        row.email = email or row.email
        if requested_name:
            row.name = requested_name
        elif not row.name:
            row.name = user_name_from_supabase(user, row.email)
    await db.commit()
    return row
