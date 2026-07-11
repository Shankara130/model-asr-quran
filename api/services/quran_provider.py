from __future__ import annotations

from typing import Any

from api.services.asr_provider import ModelUnavailable

_quran: Any = None


def get_quran() -> Any:
    """Lazy singleton for QuranService (loads the phoneme map under external/)."""
    global _quran
    if _quran is not None:
        return _quran

    from web.services.quran_service import QuranService

    try:
        _quran = QuranService()
    except FileNotFoundError as exc:
        raise ModelUnavailable("Peta fonem target belum tersedia di server ini.") from exc
    return _quran
