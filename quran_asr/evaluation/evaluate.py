"""Standalone evaluation harness: WER/CER (diacritized + plain) on a split, with
a per-reciter breakdown, plus word-level correct/skipped/extra rates from the
Corrector.

The per-reciter lens expose speaker overfit: if WER is much worse for an unseen
reciter than a seen one, the model has not generalized.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import jiwer
import torch

from quran_asr.alignment.corrector import load_corrector
from quran_asr.data_pipeline.normalize import strip_diacritics


def _greedy_decode(model, processor, batch_audio, device, sr: int = 16000) -> list[str]:
    inputs = processor(batch_audio, sampling_rate=sr, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(inputs.input_values.to(device)).logits
    ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(ids)


def _wer_cer(refs: list[str], hyps: list[str]) -> dict[str, float]:
    refs_p = [strip_diacritics(r) for r in refs]
    hyps_p = [strip_diacritics(h) for h in hyps]
    return {
        "wer": float(jiwer.wer(refs, hyps)),
        "cer": float(jiwer.cer(refs, hyps)),
        "wer_plain": float(jiwer.wer(refs_p, hyps_p)),
        "cer_plain": float(jiwer.cer(refs_p, hyps_p)),
        "n": len(refs),
    }


def evaluate(
    cfg,
    model_dir: str | Path | None = None,
    split: str = "test",
    batch_size: int = 8,
    corrector_sample: int = 50,
) -> dict[str, Any]:
    from datasets import load_from_disk
    from transformers import Wav2Vec2ForCTC

    from quran_asr.tokenizer.processor import build_processor

    dd = load_from_disk(cfg.data.processed_dir)
    ds = dd[split]
    processor = build_processor(cfg.model.vocab_path, cfg.data.sample_rate)

    root = Path(model_dir or cfg.logging.output_dir)
    final = root / "final" if (root / "final").exists() else root
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Wav2Vec2ForCTC.from_pretrained(str(final)).to(device).eval()

    # decode in batches, grouping refs/hyps by reciter
    by_reciter_refs: dict[str, list[str]] = defaultdict(list)
    by_reciter_hyps: dict[str, list[str]] = defaultdict(list)
    for i in range(0, len(ds), batch_size):
        batch = ds[i:i + batch_size]
        from quran_asr.audio_io import load_audio

        audios = [load_audio(p, cfg.data.sample_rate)[0] for p in batch["audio_path"]]
        hyps = _greedy_decode(model, processor, audios, device, cfg.data.sample_rate)
        for reciter, ref, hyp in zip(batch["reciter"], batch["text"], hyps, strict=True):
            by_reciter_refs[reciter].append(ref)
            by_reciter_hyps[reciter].append(hyp)

    results: dict[str, Any] = {"split": split, "per_reciter": {}}
    all_refs, all_hyps = [], []
    for reciter in sorted(by_reciter_refs):
        m = _wer_cer(by_reciter_refs[reciter], by_reciter_hyps[reciter])
        results["per_reciter"][reciter] = m
        all_refs.extend(by_reciter_refs[reciter])
        all_hyps.extend(by_reciter_hyps[reciter])
    results["overall"] = _wer_cer(all_refs, all_hyps)

    # word-level corrector rates on a sample
    results["word_level"] = _corrector_rates(final, processor, ds, cfg, corrector_sample)
    return results


def _corrector_rates(model_dir, processor, ds, cfg, sample: int) -> dict[str, float]:
    corrector = load_corrector(model_dir)
    counts = {"correct": 0, "low_confidence": 0, "skipped": 0, "extra": 0}
    total = 0
    n = min(sample, len(ds))
    for i in range(n):
        ex = ds[i]
        from quran_asr.audio_io import load_audio

        audio, sr = load_audio(ex["audio_path"], cfg.data.sample_rate)
        words = corrector.correct(audio, sr, ex["text"])
        for w in words:
            counts[w.status] += 1
            total += 1
    if total == 0:
        return {"note": "no words aligned"}
    return {k: v / total for k, v in counts.items()}


def save_results(results: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    return path
