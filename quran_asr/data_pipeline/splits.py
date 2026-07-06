"""Anti-memorization split strategies.

The Quran is a fixed closed vocabulary, so a random per-ayah split lets the model
memorize fixed verses and report falsely good WER. Two acceptable strategies:

  * ``by_surah`` — hold out whole surahs for test/val. The model is tested on
    verses whose exact word sequence it never trained on.
  * ``by_reciter`` — train on reciter A, test on reciter B (needs >=2 reciters).
    A cross-speaker lens: measures generalization to *the user's* voice.

Never: a random per-ayah split, or the same (surah, ayah, reciter) triple in two
splits. :func:`assert_no_triple_leak` guards the latter.
"""

from __future__ import annotations

import random
from typing import Any

from quran_asr.config import SplitConfig


def split_by_surah(
    meta: list[dict[str, Any]],
    test_surahs: list[int],
    val_surahs: list[int],
    val_frac_within_train: float,
    seed: int = 42,
) -> dict[str, list[int]]:
    test_set, val_set = set(test_surahs), set(val_surahs)
    train_pool: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []
    for i, m in enumerate(meta):
        if m["surah"] in test_set:
            test_idx.append(i)
        elif val_set and m["surah"] in val_set:
            val_idx.append(i)
        else:
            train_pool.append(i)

    rng = random.Random(seed)
    rng.shuffle(train_pool)
    if not val_set and val_frac_within_train > 0:
        n = int(len(train_pool) * val_frac_within_train)
        val_idx, train_pool = train_pool[:n], train_pool[n:]
    return {"train": train_pool, "validation": val_idx, "test": test_idx}


def split_by_reciter(
    meta: list[dict[str, Any]],
    test_reciter: str,
    val_frac_within_train: float,
    seed: int = 42,
) -> dict[str, list[int]]:
    test_idx = [i for i, m in enumerate(meta) if m["reciter"] == test_reciter]
    pool = [i for i, m in enumerate(meta) if m["reciter"] != test_reciter]
    rng = random.Random(seed)
    rng.shuffle(pool)
    n = int(len(pool) * val_frac_within_train)
    return {"train": pool[n:], "validation": pool[:n], "test": test_idx}


def make_splits(
    meta: list[dict[str, Any]],
    split_cfg: SplitConfig,
    reciters: list[str] | None = None,
    seed: int = 42,
) -> dict[str, list[int]]:
    if split_cfg.strategy == "by_surah":
        return split_by_surah(meta, split_cfg.test_surahs, split_cfg.val_surahs,
                              split_cfg.val_frac_within_train, seed)
    if split_cfg.strategy == "by_reciter":
        if split_cfg.test_reciter is None:
            raise ValueError("split.strategy='by_reciter' requires split.test_reciter")
        if reciters is not None and len(set(reciters)) < 2:
            raise ValueError("by_reciter needs >=2 distinct reciters")
        return split_by_reciter(meta, split_cfg.test_reciter,
                                split_cfg.val_frac_within_train, seed)
    raise ValueError(f"unknown split strategy: {split_cfg.strategy}")


def assert_no_triple_leak(meta: list[dict[str, Any]], splits: dict[str, list[int]]) -> None:
    """No (surah, ayah, reciter) triple may appear in two splits."""
    seen: dict[tuple[int, int, str], str] = {}
    for split_name, idxs in splits.items():
        for i in idxs:
            m = meta[i]
            key = (m["surah"], m["ayah"], m["reciter"])
            if key in seen:
                raise AssertionError(f"{key} leaked: {seen[key]} and {split_name}")
            seen[key] = split_name
