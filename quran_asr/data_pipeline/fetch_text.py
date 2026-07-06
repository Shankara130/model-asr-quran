"""Fetch fully-diacritized Uthmani Quran text from the quran.com API and cache it.

The bulk endpoint returns all 6236 verses in one request. Text↔audio alignment is
a trivial 1:1 map per (surah, ayah), so we only need the text keyed by (surah, ayah).
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

QURAN_COM_UTHMANI_URL = "https://api.quran.com/api/v4/quran/verses/uthmani"
_TIMEOUT = 30


def _parse_key(key: str) -> tuple[int, int]:
    surah, ayah = key.split(":")
    return int(surah), int(ayah)


def fetch_uthmani(
    out_path: str | Path,
    url: str = QURAN_COM_UTHMANI_URL,
    timeout: int = _TIMEOUT,
    force: bool = False,
) -> dict[tuple[int, int], str]:
    """Return ``{(surah, ayah): diacritized_text}``; cache to ``out_path`` as JSON.

    Reuses the cached file unless ``force`` (re-download)."""
    out_path = Path(out_path)
    if out_path.exists() and not force:
        return load_uthmani(out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    mapping: dict[tuple[int, int], str] = {}
    for v in data["verses"]:
        mapping[_parse_key(v["verse_key"])] = v["text_uthmani"]

    # Store with "S:A" string keys for human-readable JSON.
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump({f"{s}:{a}": t for (s, a), t in sorted(mapping.items())}, fh,
                  ensure_ascii=False, indent=1)
    return mapping


def load_uthmani(path: str | Path) -> dict[tuple[int, int], str]:
    """Load the cached JSON cache produced by :func:`fetch_uthmani`."""
    with Path(path).open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return {_parse_key(k): t for k, t in raw.items()}


def all_ayah_keys() -> list[tuple[int, int]]:
    """All 6236 (surah, ayah) keys in canonical order."""
    # ayah counts per surah (1-indexed); used to enumerate every verse.
    # Verified to sum to 6236 against the quran.com Uthmani corpus.
    surah_lengths = [
        7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
        111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
        54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
        49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
        44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
        26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
        6, 3, 5, 4, 5, 6,
    ]
    keys: list[tuple[int, int]] = []
    for surah, n_ayah in enumerate(surah_lengths, start=1):
        keys.extend((surah, ayah) for ayah in range(1, n_ayah + 1))
    assert len(keys) == 6236, f"expected 6236 ayat, got {len(keys)}"
    return keys
