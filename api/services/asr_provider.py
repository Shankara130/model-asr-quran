from __future__ import annotations

from typing import Any

from api.core.errors import ApiError

_asr: Any = None


class ModelUnavailable(ApiError):
    """Raised when the ONNX model / phoneme map is missing on this host."""

    def __init__(self, message: str = "Model ASR belum tersedia di server ini.") -> None:
        super().__init__(
            "audio_unprocessable",
            message,
            details={"model_missing": True},
        )


def get_asr() -> Any:
    """Lazy singleton for ASRService. Raises ModelUnavailable if the model is absent."""
    global _asr
    if _asr is not None:
        return _asr

    from web.config import validate_required_files

    try:
        validate_required_files()
    except FileNotFoundError as exc:
        raise ModelUnavailable() from exc

    from web.services.asr_service import ASRService

    _asr = ASRService()
    return _asr
