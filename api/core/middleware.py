from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from api.core.context import set_request_id, set_user_id
from api.core.errors import ERROR_STATUS, ApiError, error_payload
from api.core.ids import new_request_id

log = logging.getLogger("api.errors")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Read or generate X-Request-Id and echo it on every response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or new_request_id()
        request.state.request_id = request_id
        set_request_id(request_id)
        set_user_id("-")

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        if exc.status >= 500:
            log.exception("internal api error: %s", exc.code)
        return JSONResponse(
            status_code=exc.status,
            content=error_payload(exc.code, exc.message, _request_id(request), exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_payload(
                "validation_failed",
                "Permintaan tidak valid.",
                _request_id(request),
                {"errors": _safe_errors(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _http_status_to_code(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail) or code, _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "internal_error", "Terjadi kesalahan internal.", _request_id(request)
            ),
        )


def _http_status_to_code(status: int) -> str:
    for code, mapped in ERROR_STATUS.items():
        if mapped == status:
            return code
    return "internal_error"


def _safe_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip potentially sensitive values (e.g. password) from validation errors."""
    safe = []
    for err in errors:
        entry = {k: v for k, v in err.items() if k != "ctx"}
        ctx = err.get("ctx") or {}
        entry["ctx"] = {
            k: ("***" if k.lower() in {"password", "token"} else v) for k, v in ctx.items()
        }
        safe.append(entry)
    return safe


def make_error_response(
    request: Request | None,
    code: str,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    status: int | None = None,
) -> JSONResponse:
    """Build a spec-shaped error response imperatively (used outside handlers)."""
    rid = _request_id(request) if request is not None else "-"
    return JSONResponse(
        status_code=status or ERROR_STATUS.get(code, 500),
        content=error_payload(
            code if code in ERROR_STATUS else "internal_error",
            message or code,
            rid,
            details,
        ),
    )


__all__ = [
    "RequestIdMiddleware",
    "register_exception_handlers",
    "make_error_response",
    "ASGIApp",
]
