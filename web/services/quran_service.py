from __future__ import annotations

import json
import random
import re
import unicodedata
from typing import Any

from web.config import PHONEME_MAP_PATH, QURAN_TEXT_PATH


def normalize_arabic(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        str(text),
    )

    normalized = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )

    normalized = normalized.replace("ـ", "")

    replacements = {
        "ٱ": "ا",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }

    for source, target in replacements.items():
        normalized = normalized.replace(
            source,
            target,
        )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def normalize_arabic_alif_insensitive(
    text: str,
) -> str:
    return normalize_arabic(text).replace("ا", "")


def normalize_phoneme(text: str) -> str:
    return "".join(str(text).split())


class QuranService:
    def __init__(self) -> None:
        self.verse_index: dict[str, str] = {}
        self.phoneme_map: dict[str, str] = {}

        self._load_data()

    def _load_data(self) -> None:
        with QURAN_TEXT_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        self.verse_index = {
            verse["verse_key"]: verse["text_uthmani"]
            for verse in payload["verses"]
        }

        with PHONEME_MAP_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            self.phoneme_map = json.load(file)

    def find_target_phoneme(
        self,
        target_text: str,
    ) -> str:
        normalized_target = normalize_arabic(
            target_text
        )

        for ayah_text, phoneme in self.phoneme_map.items():
            if (
                normalize_arabic(ayah_text)
                == normalized_target
            ):
                return phoneme

        fallback_target = (
            normalize_arabic_alif_insensitive(
                target_text
            )
        )

        matches = [
            phoneme
            for ayah_text, phoneme
            in self.phoneme_map.items()
            if normalize_arabic_alif_insensitive(
                ayah_text
            )
            == fallback_target
        ]

        if len(matches) == 1:
            return matches[0]

        if not matches:
            raise KeyError(
                "Fonem target ayat tidak ditemukan."
            )

        raise KeyError(
            "Fonem target ambigu setelah normalisasi."
        )

    def get_verse(
        self,
        surah: int,
        ayah: int,
    ) -> dict[str, Any]:
        verse_key = f"{surah}:{ayah}"
        target_text = self.verse_index.get(verse_key)

        if target_text is None:
            raise KeyError(
                f"Surah {surah} ayat {ayah} "
                "tidak ditemukan."
            )

        target_phoneme = self.find_target_phoneme(
            target_text
        )

        return {
            "surah": surah,
            "ayah": ayah,
            "target_text": target_text,
            "target_phoneme": target_phoneme,
        }

    def get_random_verse(
        self,
    ) -> dict[str, Any]:
        verse_keys = list(self.verse_index.keys())

        for _ in range(100):
            verse_key = random.choice(verse_keys)
            target_text = self.verse_index[verse_key]

            try:
                target_phoneme = (
                    self.find_target_phoneme(
                        target_text
                    )
                )
            except KeyError:
                continue

            surah, ayah = map(
                int,
                verse_key.split(":"),
            )

            return {
                "surah": surah,
                "ayah": ayah,
                "target_text": target_text,
                "target_phoneme": target_phoneme,
            }

        raise RuntimeError(
            "Tidak berhasil memilih ayat random."
        )