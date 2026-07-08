"""Reference text helpers for Quran ASR inference."""

from __future__ import annotations

from pathlib import Path

from quran_asr.data_pipeline.fetch_text import load_uthmani
from quran_asr.data_pipeline.normalize import normalize


def resolve_reference(
    text_path: str | Path,
    surah: int | None = None,
    ayah: int | None = None,
    reference: str | None = None,
) -> str | None:
    """Resolve a target transcript for evaluation/correction.

    A manually supplied ``reference`` wins. Otherwise both ``surah`` and ``ayah``
    are required, and the text is loaded from the cached Uthmani Quran JSON.
    """
    if reference:
        return normalize(reference)
    if surah is None and ayah is None:
        return None
    if surah is None or ayah is None:
        raise ValueError("--surah and --ayah must be provided together")

    mapping = load_uthmani(text_path)
    key = (int(surah), int(ayah))
    if key not in mapping:
        raise KeyError(f"ayah not found in Uthmani text: {surah}:{ayah}")
    return normalize(mapping[key])
