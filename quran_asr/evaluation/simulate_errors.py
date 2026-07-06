"""Synthetic error injection to measure Corrector recall.

Real mispronunciations are scarce in labeled form, so we take clean
(audio, reference) pairs and perturb the *reference* text (audio untouched),
then check whether the Corrector surfaces a low-confidence / skipped word. This
estimates how well the corrector catches learner-style mistakes.

Note: this measures recall of the *forced-alignment* path. It cannot exercise
``extra`` (added-word) detection, which needs the free-running ASR path.
"""

from __future__ import annotations

import random

from quran_asr.alignment.corrector import Corrector

_SWAP = {"َ": "ُ", "ُ": "َ", "ِ": "ُ", "ً": "ٌ", "ٌ": "ً"}  # fatha<->damma, etc.


def delete_word(text: str, rng: random.Random) -> tuple[str, int]:
    """Remove one word; return (new_text, index_removed)."""
    words = text.split()
    if len(words) < 2:
        return text, -1
    i = rng.randrange(len(words))
    return " ".join(words[:i] + words[i + 1:]), i


def mutate_harakat(text: str, rng: random.Random) -> tuple[str, int]:
    """Swap one haraka for a different one; return (new_text, char_index). or (-1)."""
    swappable = [(i, ch) for i, ch in enumerate(text) if ch in _SWAP]
    if not swappable:
        return text, -1
    i, ch = rng.choice(swappable)
    return text[:i] + _SWAP[ch] + text[i + 1:], i


def measure_recall(corrector: Corrector, examples, sr: int, n: int = 50,
                   seed: int = 0) -> dict[str, float]:
    """For each error type, fraction of cases where the corrector flags something."""
    rng = random.Random(seed)
    hit = {"delete_word": 0, "mutate_harakat": 0}
    total = {"delete_word": 0, "mutate_harakat": 0}

    for ex in examples[:n]:
        ref = ex["text"]
        audio = ex["audio"]["array"] if isinstance(ex.get("audio"), dict) else ex["audio"]
        for kind, fn in (("delete_word", delete_word), ("mutate_harakat", mutate_harakat)):
            new_ref, idx = fn(ref, rng)
            if idx < 0:
                continue
            total[kind] += 1
            words = corrector.correct(audio, sr, new_ref)
            # "flagged" = any non-correct word (the perturbation should stand out)
            if any(w.status != "correct" for w in words):
                hit[kind] += 1

    return {k: (hit[k] / total[k] if total[k] else 0.0) for k in hit}
