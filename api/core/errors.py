from __future__ import annotations

from typing import Any

# Map of error code -> HTTP status (BackendRequirements.md §4).
ERROR_STATUS: dict[str, int] = {
    "auth_invalid_credentials": 401,
    "auth_token_expired": 401,
    "auth_refresh_failed": 401,
    "websocket_unauthorized": 401,
    "forbidden": 403,
    "validation_failed": 400,
    "profile_update_failed": 400,
    "audio_upload_failed": 400,
    "audio_chunk_missing": 400,
    "practice_not_found": 404,
    "session_not_found": 404,
    "insight_not_ready": 404,
    "session_invalid_state": 409,
    "auth_email_exists": 409,
    "auth_identity_conflict": 409,
    "payload_too_large": 413,
    "audio_unprocessable": 422,
    "rate_limited": 429,
    "auth_service_unavailable": 503,
    "evaluation_failed": 500,
    "internal_error": 500,
}

DEFAULT_MESSAGES: dict[str, str] = {
    "auth_invalid_credentials": "Email atau kata sandi tidak valid.",
    "auth_token_expired": "Access token tidak valid atau sudah kedaluwarsa.",
    "auth_refresh_failed": "Refresh token tidak valid atau sudah dicabut.",
    "websocket_unauthorized": "Realtime token tidak valid atau bukan milik sesi ini.",
    "forbidden": "Anda tidak memiliki akses ke resource ini.",
    "validation_failed": "Permintaan tidak valid.",
    "profile_update_failed": "Gagal memperbarui profil.",
    "audio_upload_failed": "Upload audio gagal.",
    "audio_chunk_missing": "Beberapa chunk audio belum diterima.",
    "audio_unprocessable": "Audio tidak dapat diproses.",
    "practice_not_found": "Item latihan tidak ditemukan.",
    "session_not_found": "Sesi latihan tidak ditemukan.",
    "insight_not_ready": "Insight belum tersedia.",
    "session_invalid_state": "Operasi tidak valid untuk status sesi ini.",
    "auth_email_exists": "Email sudah terdaftar.",
    "auth_identity_conflict": "Identitas akun bertentangan dengan profil yang sudah ada.",
    "payload_too_large": "Ukuran payload terlalu besar.",
    "rate_limited": "Terlalu banyak permintaan.",
    "auth_service_unavailable": (
        "Layanan autentikasi sedang tidak dapat dijangkau. Periksa koneksi lalu coba lagi."
    ),
    "evaluation_failed": "Evaluasi gagal.",
    "internal_error": "Terjadi kesalahan internal.",
}


class ApiError(Exception):
    """Domain error that maps to the spec's standard error shape (§4)."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        status_override: int | None = None,
    ) -> None:
        self.code = code if code in ERROR_STATUS else "internal_error"
        self.message = message or DEFAULT_MESSAGES.get(self.code, "Terjadi kesalahan.")
        self.details = details or {}
        self.status = status_override or ERROR_STATUS[self.code]
        super().__init__(self.message)


def error_payload(
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id,
            "details": details or {},
        }
    }
