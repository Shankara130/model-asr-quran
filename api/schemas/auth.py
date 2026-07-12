from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class UserPublic(CamelModel):
    id: str = Field(description="Stable user id.")
    name: str = Field(description="Display name.")
    email: str = Field(description="Unique email.")
    avatar_url: str | None = Field(default=None, description="Avatar URL, if set.")
    learning_level: str = Field(
        default="beginner",
        description="beginner | intermediate | advanced.",
    )
    created_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp.")


class Tokens(CamelModel):
    access_token: str = Field(description="Short-lived Bearer access token.")
    refresh_token: str = Field(description="Opaque refresh token; rotated on each refresh.")
    expires_in: int = Field(description="Access token lifetime in seconds.")


class SignupRequest(CamelModel):
    name: str = Field(description="Display name.", examples=["Alya Rahma"])
    email: str = Field(description="Unique email.", examples=["alya@sobat.ngaji"])
    password: str = Field(
        description="Password for Supabase Auth or local dev fallback.",
        examples=["password123"],
    )


class LoginRequest(CamelModel):
    email: str = Field(description="Registered email.", examples=["alya@sobat.ngaji"])
    password: str = Field(
        description="Password for Supabase Auth or any value in local dev fallback.",
        examples=["password123"],
    )


class RefreshRequest(CamelModel):
    refresh_token: str = Field(description="Refresh token from a previous login/refresh.")


class LogoutRequest(CamelModel):
    refresh_token: str = Field(description="Refresh token to revoke.")


class AuthResponse(CamelModel):
    user: UserPublic
    tokens: Tokens


class MeResponse(CamelModel):
    user: UserPublic


class RefreshResponse(CamelModel):
    access_token: str = Field(description="New short-lived access token.")
    refresh_token: str = Field(description="New rotated refresh token.")
    expires_in: int


class LogoutResponse(CamelModel):
    success: bool = Field(default=True, description="Logout completed best-effort.")
