"""Interactive launcher helpers for local Quran ASR workflows."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from quran_asr.data_pipeline.fetch_text import load_uthmani

DEFAULT_HF_MODEL = "TBOGamer22/wav2vec2-quran-phonetics"
LOCAL_BEST_MODEL = "data/artifacts/checkpoints/local_3050_small/best"
LOCAL_LATEST_MODEL = "data/artifacts/checkpoints/local_3050_small/latest"
LOCAL_CONFIG = "configs/local_3050.yaml"
TEXT_PATH = "data/raw/text/quran_uthmani.json"

SURAH_NAMES = (
    "Al-Fatihah",
    "Al-Baqarah",
    "Ali Imran",
    "An-Nisa",
    "Al-Ma'idah",
    "Al-An'am",
    "Al-A'raf",
    "Al-Anfal",
    "At-Tawbah",
    "Yunus",
    "Hud",
    "Yusuf",
    "Ar-Ra'd",
    "Ibrahim",
    "Al-Hijr",
    "An-Nahl",
    "Al-Isra",
    "Al-Kahf",
    "Maryam",
    "Taha",
    "Al-Anbiya",
    "Al-Hajj",
    "Al-Mu'minun",
    "An-Nur",
    "Al-Furqan",
    "Ash-Shu'ara",
    "An-Naml",
    "Al-Qasas",
    "Al-Ankabut",
    "Ar-Rum",
    "Luqman",
    "As-Sajdah",
    "Al-Ahzab",
    "Saba",
    "Fatir",
    "Ya-Sin",
    "As-Saffat",
    "Sad",
    "Az-Zumar",
    "Ghafir",
    "Fussilat",
    "Ash-Shura",
    "Az-Zukhruf",
    "Ad-Dukhan",
    "Al-Jathiyah",
    "Al-Ahqaf",
    "Muhammad",
    "Al-Fath",
    "Al-Hujurat",
    "Qaf",
    "Adh-Dhariyat",
    "At-Tur",
    "An-Najm",
    "Al-Qamar",
    "Ar-Rahman",
    "Al-Waqi'ah",
    "Al-Hadid",
    "Al-Mujadilah",
    "Al-Hashr",
    "Al-Mumtahanah",
    "As-Saff",
    "Al-Jumu'ah",
    "Al-Munafiqun",
    "At-Taghabun",
    "At-Talaq",
    "At-Tahrim",
    "Al-Mulk",
    "Al-Qalam",
    "Al-Haqqah",
    "Al-Ma'arij",
    "Nuh",
    "Al-Jinn",
    "Al-Muzzammil",
    "Al-Muddaththir",
    "Al-Qiyamah",
    "Al-Insan",
    "Al-Mursalat",
    "An-Naba",
    "An-Nazi'at",
    "Abasa",
    "At-Takwir",
    "Al-Infitar",
    "Al-Mutaffifin",
    "Al-Inshiqaq",
    "Al-Buruj",
    "At-Tariq",
    "Al-A'la",
    "Al-Ghashiyah",
    "Al-Fajr",
    "Al-Balad",
    "Ash-Shams",
    "Al-Layl",
    "Ad-Duha",
    "Ash-Sharh",
    "At-Tin",
    "Al-Alaq",
    "Al-Qadr",
    "Al-Bayyinah",
    "Az-Zalzalah",
    "Al-Adiyat",
    "Al-Qari'ah",
    "At-Takathur",
    "Al-Asr",
    "Al-Humazah",
    "Al-Fil",
    "Quraysh",
    "Al-Ma'un",
    "Al-Kawthar",
    "Al-Kafirun",
    "An-Nasr",
    "Al-Masad",
    "Al-Ikhlas",
    "Al-Falaq",
    "An-Nas",
)


@dataclass(frozen=True)
class SurahChoice:
    number: int
    name: str
    ayah_count: int


def load_surah_choices(text_path: str | Path = TEXT_PATH) -> list[SurahChoice]:
    """Load available surah choices and ayah counts from the local Uthmani JSON."""
    mapping = load_uthmani(text_path)
    counts: dict[int, int] = {}
    for surah, ayah in mapping:
        counts[surah] = max(counts.get(surah, 0), ayah)
    return [
        SurahChoice(number=i, name=SURAH_NAMES[i - 1], ayah_count=counts[i])
        for i in sorted(counts)
    ]


def filter_surahs(choices: list[SurahChoice], query: str) -> list[SurahChoice]:
    """Filter surah menu by number or case-insensitive name substring."""
    normalized = query.strip().lower()
    if not normalized:
        return choices
    if normalized.isdigit():
        return [choice for choice in choices if choice.number == int(normalized)]
    return [choice for choice in choices if normalized in choice.name.lower()]


def build_live_infer_command(
    *,
    model: str,
    surah: int,
    ayah: int,
    audio: str | None = None,
    live: bool = False,
    record_seconds: float | None = None,
    chunk_seconds: float | None = None,
    device: str = "auto",
) -> list[str]:
    """Build the command used by the launcher for ASR inference."""
    cmd = [
        sys.executable,
        "scripts/live_infer_asr.py",
        "--model",
        model,
        "--surah",
        str(surah),
        "--ayah",
        str(ayah),
        "--device",
        device,
    ]
    if audio:
        cmd.extend(["--audio", audio])
    if live:
        cmd.append("--live")
    if record_seconds is not None:
        cmd.extend(["--record-seconds", _format_number(record_seconds)])
    if chunk_seconds is not None:
        cmd.extend(["--chunk-seconds", _format_number(chunk_seconds)])
    return cmd


def build_train_command(*, resume: bool, config: str = LOCAL_CONFIG) -> list[str]:
    """Build the command used by the launcher for local manual training."""
    cmd = [sys.executable, "scripts/train_manual.py", "--config", config]
    if not resume:
        cmd.append("--no-resume")
    return cmd


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
