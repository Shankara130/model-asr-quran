"""Aggregate token boundaries into word boundaries.

Harakat are separate CTC tokens; a "word" is the run of tokens between
word-delimiter (``|``) tokens. The word's text is the char-join of its tokens,
its span covers the first..last token, and its confidence is the mean token
score (geometric mean of per-frame probs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quran_asr.alignment.forced_align import TokenBoundary


@dataclass
class WordBoundary:
    text: str
    start: float
    end: float
    confidence: float  # geometric-mean prob in [0, 1]
    index: int         # position among the aligned words


def _word_delimiter_id(processor: Any) -> int:
    return processor.tokenizer.convert_tokens_to_ids(processor.tokenizer.word_delimiter_token)


def tokens_to_words(
    boundaries: list[TokenBoundary], processor: Any,
) -> list[WordBoundary]:
    delim = _word_delimiter_id(processor)
    words: list[WordBoundary] = []
    cur: list[TokenBoundary] = []

    def flush(idx: int) -> None:
        if not cur:
            return
        tokens = processor.tokenizer.convert_ids_to_tokens([b.token_id for b in cur])
        text = "".join(t for t in tokens if t != "|")
        conf = _geomean([b.score for b in cur])
        words.append(WordBoundary(
            text=text, start=cur[0].start, end=cur[-1].end, confidence=conf, index=idx,
        ))

    idx = 0
    for b in boundaries:
        if b.token_id == delim:
            flush(idx)
            idx += 1
            cur = []
        else:
            cur.append(b)
    flush(idx)
    return words


def _geomean(log_probs: list[float]) -> float:
    import math

    if not log_probs:
        return 0.0
    m = sum(log_probs) / len(log_probs)
    return math.exp(m)
