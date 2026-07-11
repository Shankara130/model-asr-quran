from __future__ import annotations

import hashlib
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.core.errors import ApiError
from api.core.ids import new_token_id
from api.settings import settings

_serializer = URLSafeTimedSerializer(settings.token_secret, salt="sobat-ngaji")


def issue_access_token(user_id: str) -> str:
    return _serializer.dumps({"sub": user_id, "typ": "access", "jti": new_token_id()})


def issue_realtime_token(user_id: str, session_id: str) -> str:
    return _serializer.dumps(
        {"sub": user_id, "sid": session_id, "typ": "realtime", "jti": new_token_id()}
    )


def _loads(token: str, max_age: int) -> dict:
    try:
        return _serializer.loads(token, max_age=max_age)
    except SignatureExpired as exc:
        raise ApiError("auth_token_expired") from exc
    except BadSignature as exc:
        raise ApiError("auth_invalid_credentials") from exc


def verify_access_token(token: str) -> dict:
    payload = _loads(token, max_age=settings.access_token_ttl_seconds)
    if payload.get("typ") != "access":
        raise ApiError("auth_token_expired")
    return payload


def verify_realtime_token(token: str, expected_session_id: str, expected_user_id: str) -> dict:
    payload = _loads(token, max_age=settings.realtime_token_ttl_seconds)
    if payload.get("typ") != "realtime":
        raise ApiError("websocket_unauthorized")
    if payload.get("sid") != expected_session_id or payload.get("sub") != expected_user_id:
        raise ApiError("websocket_unauthorized")
    return payload


# --- Mock refresh tokens: opaque random, stored as sha256 digest at rest (§15). ---


def generate_refresh_token() -> str:
    return f"rt_{secrets.token_urlsafe(32)}"


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
