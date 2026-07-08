"""Reusable inference helpers for interactive Quran ASR testing."""

from __future__ import annotations

import difflib
import time
from dataclasses import dataclass
from typing import Any

import jiwer

from quran_asr.data_pipeline.normalize import strip_diacritics


@dataclass(frozen=True)
class DecodeResult:
    text: str
    latency_ms: float
    confidence: float
    non_blank_confidence: float
    blank_rate: float
    top_tokens: list[tuple[int, str, float]]


def compute_text_metrics(reference: str, hypothesis: str) -> dict[str, float]:
    """Compute diacritized and plain WER/CER for a single utterance."""
    ref_plain = strip_diacritics(reference)
    hyp_plain = strip_diacritics(hypothesis)
    return {
        "wer": float(jiwer.wer(reference, hypothesis)),
        "cer": float(jiwer.cer(reference, hypothesis)),
        "wer_plain": float(jiwer.wer(ref_plain, hyp_plain)),
        "cer_plain": float(jiwer.cer(ref_plain, hyp_plain)),
    }


def format_correction(reference: str, hypothesis: str) -> str:
    """Return a compact word-level diff between target and prediction."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    diff = difflib.ndiff(ref_words, hyp_words)
    return " ".join(diff)


def decode_audio(
    model: Any,
    processor: Any,
    audio: list[float],
    sample_rate: int,
    device: Any,
    top_k: int = 8,
) -> DecodeResult:
    """Run greedy CTC inference and expose debugging signals."""
    import torch

    started = time.perf_counter()
    inputs = processor(audio, sampling_rate=sample_rate, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)

    pred_ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(pred_ids)[0]
    latency_ms = (time.perf_counter() - started) * 1000.0

    frame_probs, frame_ids = probs.max(dim=-1)
    blank_id = processor.tokenizer.pad_token_id
    blank_mask = frame_ids == blank_id
    blank_rate = float(blank_mask.float().mean().item()) if blank_id is not None else 0.0
    confidence = float(frame_probs.mean().item())
    non_blank = frame_probs[~blank_mask]
    non_blank_confidence = float(non_blank.mean().item()) if non_blank.numel() else 0.0

    avg_probs = probs[0].mean(dim=0)
    k = min(int(top_k), avg_probs.numel())
    top = avg_probs.topk(k)
    tokens = processor.tokenizer.convert_ids_to_tokens(top.indices.tolist())
    top_tokens = [
        (int(idx), str(tok), float(prob))
        for idx, tok, prob in zip(top.indices.tolist(), tokens, top.values.tolist(), strict=True)
    ]

    return DecodeResult(
        text=text,
        latency_ms=latency_ms,
        confidence=confidence,
        non_blank_confidence=non_blank_confidence,
        blank_rate=blank_rate,
        top_tokens=top_tokens,
    )
