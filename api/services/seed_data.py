from __future__ import annotations

import json
import logging
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PracticeItem
from api.settings import PROJECT_ROOT, QURAN_TEXT_PATH
from api.static_data import SURAH_BY_NUMBER

log = logging.getLogger("api.seed")

# Reuse the engine's existing letter drills (pure-python, model-independent).
from web.services.letter_test_service import LETTER_TESTS  # noqa: E402

try:
    from quran_asr.tajwid.interpreter import ARABIC_LETTERS  # noqa: E402
except Exception:  # pragma: no cover - interpreter is pure-python, always present
    ARABIC_LETTERS = set("ابتثجحخدذرزسشصضطظعغفقكلمنهويء")

JUZ_30_RANGE = range(78, 115)  # 78..114
MAX_AYAH_CHARS = 60


def _segments(text: str) -> list[dict[str, Any]]:
    """Split arabic_text on whitespace into {index,text,startChar,endChar}."""
    segments: list[dict[str, Any]] = []
    idx = 0
    pos = 0
    for token in text.split():
        start = text.find(token, pos)
        if start == -1:
            start = pos
        segments.append(
            {"index": idx, "text": token, "startChar": start, "endChar": start + len(token)}
        )
        pos = start + len(token)
        idx += 1
    return segments


def _first_focus_letter(text: str) -> str | None:
    for char in text:
        if char in ARABIC_LETTERS:
            return char
    return None


def _level_for(word_count: int) -> str:
    if word_count <= 2:
        return "beginner"
    if word_count <= 5:
        return "intermediate"
    return "advanced"


def _load_verses() -> dict[str, str]:
    if QURAN_TEXT_PATH.exists():
        with QURAN_TEXT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    # Fresh-clone fallback: a tiny built-in Al-Fatihah set.
    log.warning("quran_uthmani.json not found at %s; using built-in fallback", QURAN_TEXT_PATH)
    return {
        "1:1": "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ",
        "1:2": "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ",
        "1:3": "ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ",
        "1:4": "مَـٰلِكِ يَوْمِ ٱلدِّينِ",
        "1:5": "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
        "1:6": "ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ",
        "1:7": "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ",
    }


def _verse_items() -> list[PracticeItem]:
    verses = _load_verses()
    items: list[PracticeItem] = []
    for key, text in verses.items():
        try:
            surah, ayah = map(int, key.split(":"))
        except ValueError:
            continue

        is_juz30 = surah in JUZ_30_RANGE
        is_fatihah = surah == 1
        if not (is_juz30 or is_fatihah):
            continue
        if len(text) > MAX_AYAH_CHARS:
            continue

        meta = SURAH_BY_NUMBER.get(surah)
        if meta is None:
            continue

        words = text.split()
        word_count = len(words)
        focus_letter = _first_focus_letter(text)

        items.append(
            PracticeItem(
                id=f"{meta['slug']}_{ayah}",
                surah_name=meta["latin_name"],
                surah_number=surah,
                ayah_label=f"Ayat {ayah}",
                ayah_number_start=ayah,
                ayah_number_end=ayah,
                arabic_name=meta["arabic_name"],
                arabic_text=text,
                translation=meta["translation"],
                latin_hint=None,
                focus=f"Huruf {focus_letter}" if focus_letter else "",
                level=_level_for(word_count),
                estimated_minutes=max(3, math.ceil(word_count / 3)),
                reference_audio_url=f"/v1/reference-audio/{surah:03d}{ayah:03d}",
                is_daily=(ayah == 1),
                tags=["juz30" if is_juz30 else "juz1"] + (["daily"] if ayah == 1 else []),
                kind="verse",
                letter_index=None,
                target_phoneme=None,
            )
        )
    return items


def _letter_items() -> list[PracticeItem]:
    items: list[PracticeItem] = []
    for test in LETTER_TESTS:
        items.append(
            PracticeItem(
                id=f"letter_{test['index']}",
                surah_name="Uji Huruf",
                surah_number=0,
                ayah_label=f"#{test['index'] + 1}",
                ayah_number_start=0,
                ayah_number_end=0,
                arabic_name="",
                arabic_text=test["display"],
                translation=None,
                latin_hint=test.get("latin_hint"),
                focus=f"Huruf {test['letter']}",
                level="beginner",
                estimated_minutes=2,
                reference_audio_url="",
                is_daily=False,
                tags=["letters"],
                kind="letter",
                letter_index=test["index"],
                target_phoneme=test["target_phoneme"],
            )
        )
    return items


async def seed_practice_items(session: AsyncSession) -> int:
    """Insert curated verse + letter practice items. Idempotent by id."""
    existing = {row[0] for row in (await session.execute(select(PracticeItem.id))).all()}
    candidates = _verse_items() + _letter_items()
    added = 0
    for item in candidates:
        if item.id in existing:
            continue
        session.add(item)
        added += 1
    if added:
        await session.commit()
        log.info("seeded %d practice items", added)
    return added


# Local import guard so seeding never hard-fails if the project tree moves.
_ = PROJECT_ROOT
