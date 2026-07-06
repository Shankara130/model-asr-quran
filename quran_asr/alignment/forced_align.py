"""CTC forced alignment of a known reference transcript to audio.

Uses ``torchaudio.functional.forced_align`` with the model's own CTC blank
(which is ``pad_token_id`` for Wav2Vec2ForCTC — verified against transformers
source). Consecutive duplicate target tokens are separated by inserting a blank
(the CTC requirement) before alignment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F


@dataclass
class TokenBoundary:
    token_id: int
    start: float   # seconds
    end: float
    score: float   # mean log-prob over the token's frames


def _prepare_targets(token_ids: list[int], blank_id: int) -> list[int]:
    """Drop blanks from the target token sequence.

    Note: torchaudio's ``forced_align`` raises if the blank id appears in targets,
    and it handles consecutive duplicate tokens internally (so we must NOT insert
    blanks between repeats)."""
    return [i for i in token_ids if i != blank_id]


def _frame_duration(model: Any, sample_rate: int) -> float:
    """Seconds per output frame = product(conv_stride) / sample_rate."""
    strides = getattr(model.config, "conv_stride", None)
    if not strides:
        return 0.02  # conservative fallback (~320 samples)
    return math.prod(strides) / sample_rate


def align(
    model: Any,
    processor: Any,
    audio: list[float],
    sample_rate: int,
    ref_text: str,
    normalizer=None,
) -> tuple[list[TokenBoundary], int]:
    """Align normalized ``ref_text`` to ``audio``; return token boundaries + n_frames."""
    from quran_asr.data_pipeline.normalize import normalize

    if normalizer is None:
        normalizer = normalize
    device = next(model.parameters()).device
    model.eval()

    inputs = processor(audio, sampling_rate=sample_rate, return_tensors="pt")
    input_values = inputs.input_values.to(device)
    with torch.no_grad():
        logits = model(input_values).logits  # [1, T, V]
    log_probs = F.log_softmax(logits, dim=-1)[0]  # [T, V]
    n_frames = log_probs.shape[0]

    blank_id = processor.tokenizer.pad_token_id
    targets = _prepare_targets(processor.tokenizer(normalizer(ref_text)).input_ids, blank_id)
    if not targets:
        return [], n_frames

    # torchaudio 2.11 forced_align expects log_probs [B, T, C] (batch-first) and
    # lacks an MPS kernel, so run it on CPU (one utterance, cheap).
    alignment, scores = _forced_align(
        log_probs.detach().cpu().unsqueeze(0),       # [1, T, V]
        torch.tensor([targets]),                     # [1, L]
        torch.tensor([n_frames]),
        torch.tensor([len(targets)]),
        blank=blank_id,
    )
    alignment = alignment[0].tolist()   # [T]
    scores = scores[0].tolist()         # [T]

    frame_dur = _frame_duration(model, sample_rate)
    boundaries = _group_tokens(alignment, scores, blank_id, frame_dur)
    return boundaries, n_frames


def _forced_align(log_probs, targets, input_lengths, target_lengths, blank):
    from torchaudio.functional import forced_align

    return forced_align(log_probs, targets, input_lengths, target_lengths, blank=blank)


def _group_tokens(
    alignment: list[int], scores: list[float], blank_id: int, frame_dur: float,
) -> list[TokenBoundary]:
    """Collapse frames into token occurrences (maximal same-id runs, skip blanks)."""
    out: list[TokenBoundary] = []
    i, T = 0, len(alignment)
    while i < T:
        tid = alignment[i]
        if tid == blank_id:
            i += 1
            continue
        j = i
        s = scores[i]
        while j + 1 < T and alignment[j + 1] == tid:
            j += 1
            s += scores[j]
        n = j - i + 1
        out.append(TokenBoundary(
            token_id=tid,
            start=i * frame_dur,
            end=(j + 1) * frame_dur,
            score=s / n,
        ))
        i = j + 1
    return out
