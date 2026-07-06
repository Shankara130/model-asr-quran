"""Normalization tests. Risk #1: this must be right before any training.

Pure unit tests (no network) use real ayah strings copied verbatim from the
quran.com Uthmani corpus. The full-corpus sweep is network-gated.
"""

from __future__ import annotations

import os

import pytest

from quran_asr.data_pipeline.normalize import (
    DEFAULT_POLICY,
    DIACRITICS,
    STRUCTURAL,
    TAJWEED,
    TATWEEL,
    WAQF,
    NormalizePolicy,
    normalize,
    strip_diacritics,
)

# Verbatim from quran.com Uthmani (kept exotic codepoints intact).
FATIHA_1 = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"  # has tatweel ـ inside ٱلرَّحْمَـٰنِ
FATIHA_7 = "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ"
IKHLAS_4 = "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ"  # has ۥ small waw + ۢ small meem (tajweed)


def _keep_set(policy: NormalizePolicy = DEFAULT_POLICY) -> frozenset[str]:
    return policy.keep_set()


def test_output_only_contains_allowed_chars():
    for s in (FATIHA_1, FATIHA_7, IKHLAS_4):
        out = normalize(s)
        keep = _keep_set()
        assert set(out) <= keep, f"unexpected chars: {set(out) - keep}"


def test_fatiha_keeps_pronounced_diacritics():
    out = normalize(FATIHA_1)
    assert "ٰ" in out          # superscript alef (long /aː/)
    assert "ّ" in out          # shadda (ٱللَّهِ / ٱلرَّحِيمِ)
    assert "ٱ" in out          # alef wasla
    assert "ِ" in out          # kasra (بِسْمِ)


def test_fatiha_strips_tatweel():
    assert TATWEEL in FATIHA_1            # sanity: the raw text has it
    out = normalize(FATIHA_1)
    assert TATWEEL not in out


def test_ikhlas_strips_tajweed_annotations():
    assert "ۥ" in IKHLAS_4 and "ۢ" in IKHLAS_4   # raw has small waw + small meem
    out = normalize(IKHLAS_4)
    assert "ۥ" not in out and "ۢ" not in out
    # but the tanween on أَحَدٌ is preserved
    assert "ٌ" in out


def test_idempotent():
    for s in (FATIHA_1, FATIHA_7, IKHLAS_4):
        once = normalize(s)
        twice = normalize(once)
        assert once == twice


def test_strip_diacritics_keeps_only_letters():
    skel = strip_diacritics(FATIHA_1)
    diac = frozenset(DIACRITICS)
    assert not (set(skel) & diac)            # no harakat in skeleton
    assert "ٱ" in skel                       # wasla is a letter, kept
    assert len(skel.split()) == 4            # four words


def test_keep_all_marks_when_configured():
    # Opting into every optional class must still yield a clean keep-set membership.
    p = NormalizePolicy(strip_tatweel=False, keep_waqf=True, keep_tajweed_marks=True,
                        keep_structural=True)
    out = normalize(IKHLAS_4, policy=p)
    keep = _keep_set(p)
    assert set(out) <= keep


# ---------------------------------------------------------------------------
# Full-corpus sweep — network-gated (opt in with RUN_NETWORK_TESTS=1).
# ---------------------------------------------------------------------------
_RUN_NETWORK = bool(os.environ.get("RUN_NETWORK_TESTS"))
network = pytest.mark.skipif(not _RUN_NETWORK, reason="set RUN_NETWORK_TESTS=1 to run")


@network
def test_full_corpus_normalizes_cleanly(tmp_path):
    from quran_asr.data_pipeline.fetch_text import fetch_uthmani

    mapping = fetch_uthmani(tmp_path / "quran_uthmani.json")
    assert len(mapping) == 6236
    keep = _keep_set()
    stripped_classes = set(TATWEEL + WAQF + TAJWEED + STRUCTURAL)
    for (surah, ayah), text in mapping.items():
        out = normalize(text)
        assert set(out) <= keep, f"bad chars at {surah}:{ayah}"
        assert not (set(out) & stripped_classes), f"unstripped symbol at {surah}:{ayah}"
        assert out.strip(), f"empty after normalize at {surah}:{ayah}"
