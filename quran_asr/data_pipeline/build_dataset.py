"""Assemble a HuggingFace ``DatasetDict`` from downloaded audio + diacritized text.

Row schema:
    audio       Audio(16kHz)         — decoded lazily, resampled on the fly
    text        str                  — diacritized, normalized (training target)
    text_plain  str                  — harakat-stripped skeleton (baseline WER)
    surah, ayah int
    reciter     str
    duration    float

Splits are assigned via :mod:`quran_asr.data_pipeline.splits`.
"""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Audio, Dataset, DatasetDict

from quran_asr.config import Config
from quran_asr.data_pipeline import splits as splits_mod
from quran_asr.data_pipeline.fetch_text import load_uthmani
from quran_asr.data_pipeline.normalize import normalize, strip_diacritics


def _read_manifest(audio_dir: str | Path, reciter: str) -> list[dict]:
    manifest = Path(audio_dir) / reciter / "manifest.jsonl"
    if not manifest.exists():
        return []
    with manifest.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def collect_rows(cfg: Config) -> tuple[list[dict], list[dict]]:
    """Build the row list + parallel lightweight metadata for splitting.

    Returns (rows, meta) in the same order, so split indices map directly."""
    text = load_uthmani(cfg.data.text_path)
    rows: list[dict] = []
    meta: list[dict] = []
    for reciter in cfg.data.reciters:
        for r in _read_manifest(cfg.data.audio_dir, reciter):
            if not r.get("ok") or r.get("status") == "missing":
                continue
            key = (r["surah"], r["ayah"])
            if key not in text:
                continue
            if r.get("duration", 0) > cfg.data.max_duration_sec:
                continue
            if not Path(r["path"]).exists():
                continue  # manifest may reference a file deleted after download
            raw_text = text[key]
            rows.append({
                "audio": r["path"],
                "text": normalize(raw_text),
                "text_plain": strip_diacritics(raw_text),
                "surah": r["surah"],
                "ayah": r["ayah"],
                "reciter": reciter,
                "duration": r["duration"],
            })
            meta.append({"surah": r["surah"], "ayah": r["ayah"], "reciter": reciter})
    return rows, meta


def build_dataset(cfg: Config) -> DatasetDict:
    rows, meta = collect_rows(cfg)
    if not rows:
        raise RuntimeError(
            "no rows collected — check that audio is downloaded (make download) and "
            "that data.text_path / data.audio_dir are correct in the config")

    ds = Dataset.from_list(rows).cast_column("audio", Audio(sampling_rate=cfg.data.sample_rate))

    split_idx = splits_mod.make_splits(meta, cfg.data.split, reciters=cfg.data.reciters,
                                       seed=cfg.seed)
    splits_mod.assert_no_triple_leak(meta, split_idx)

    dd = DatasetDict({name: ds.select(idxs) for name, idxs in split_idx.items() if idxs})
    return dd
