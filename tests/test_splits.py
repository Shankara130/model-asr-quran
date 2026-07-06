"""Anti-memorization split tests (pure, no network)."""

from __future__ import annotations

import pytest

from quran_asr.config import SplitConfig
from quran_asr.data_pipeline import splits as S


def _meta(n_per=(10, 8, 6, 5, 4), reciter: str = "A") -> list[dict]:
    out: list[dict] = []
    for s, n in enumerate(n_per, 1):
        for a in range(1, n + 1):
            out.append({"surah": s, "ayah": a, "reciter": reciter})
    return out


def test_by_surah_holds_out_whole_surahs():
    meta = _meta()
    sp = S.make_splits(meta, SplitConfig(strategy="by_surah", test_surahs=[4],
                                         val_surahs=[5], val_frac_within_train=0.0))
    train_surahs = {meta[i]["surah"] for i in sp["train"]}
    assert 4 not in train_surahs and 5 not in train_surahs
    assert {meta[i]["surah"] for i in sp["test"]} == {4}
    assert {meta[i]["surah"] for i in sp["validation"]} == {5}
    S.assert_no_triple_leak(meta, sp)


def test_by_surah_val_frac_when_no_val_surahs():
    meta = _meta()
    sp = S.make_splits(meta, SplitConfig(strategy="by_surah", test_surahs=[5],
                                         val_surahs=[], val_frac_within_train=0.5))
    assert len(sp["validation"]) > 0
    # no overlap between train and validation
    assert not (set(sp["train"]) & set(sp["validation"]))
    S.assert_no_triple_leak(meta, sp)


def test_by_reciter_cross_speaker():
    meta = []
    for rec in ["A", "B"]:
        for a in range(1, 6):
            meta.append({"surah": 1, "ayah": a, "reciter": rec})
    sp = S.make_splits(meta, SplitConfig(strategy="by_reciter", test_reciter="B",
                                         val_frac_within_train=0.2), reciters=["A", "B"])
    assert all(meta[i]["reciter"] == "B" for i in sp["test"])
    assert all(meta[i]["reciter"] == "A" for i in sp["train"])
    S.assert_no_triple_leak(meta, sp)


def test_by_reciter_requires_two_reciters():
    meta = _meta(reciter="A")
    with pytest.raises(ValueError):
        S.make_splits(meta, SplitConfig(strategy="by_reciter", test_reciter="A"),
                      reciters=["A"])


def test_triple_leak_guard_fires():
    meta = _meta()
    leaky = {"train": [0], "test": [0]}  # same index in two splits
    with pytest.raises(AssertionError):
        S.assert_no_triple_leak(meta, leaky)
