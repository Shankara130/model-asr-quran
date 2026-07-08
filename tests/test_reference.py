from pathlib import Path

import pytest

from quran_asr.reference import resolve_reference

TEXT_PATH = Path("data/raw/text/quran_uthmani.json")


def test_manual_reference_wins():
    assert resolve_reference(TEXT_PATH, surah=1, ayah=1, reference=" أَلَمْ ") == "أَلَمْ"


def test_resolve_uthmani_reference_by_surah_ayah():
    assert resolve_reference(TEXT_PATH, surah=94, ayah=1) == "أَلَمْ نَشْرَحْ لَكَ صَدْرَكَ"


def test_surah_and_ayah_must_be_together():
    with pytest.raises(ValueError, match="--surah and --ayah"):
        resolve_reference(TEXT_PATH, surah=94)
