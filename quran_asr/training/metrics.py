"""WER/CER metrics for diacritized + plain Arabic.

Labels are decoded WITHOUT CTC collapse (a raw char join) so that geminated
consonants — the doubled ل in ٱللَّهِ — are not lost from the reference.
Predictions are decoded WITH CTC grouping via ``processor.batch_decode``.
"""

from __future__ import annotations

from typing import Any

import jiwer

from quran_asr.data_pipeline.normalize import strip_diacritics
from quran_asr.tokenizer.build_vocab import UNK_TOKEN, WORD_DELIMITER


def decode_labels_no_collapse(ids: list[int], processor: Any) -> str:
    """Char-join of label ids with no CTC grouping (preserves doubled letters)."""
    pad = processor.tokenizer.pad_token_id
    keep = [i for i in ids if i != -100 and i != pad]
    tokens = processor.tokenizer.convert_ids_to_tokens(keep)
    pieces: list[str] = []
    for t in tokens:
        if t == WORD_DELIMITER:
            pieces.append(" ")
        elif t in (UNK_TOKEN, "[PAD]"):
            continue
        else:
            pieces.append(t)
    return " ".join("".join(pieces).split())


def make_compute_metrics(processor: Any):
    def compute(pred) -> dict[str, float]:
        import numpy as np

        pred_logits = pred.predictions
        pred_ids = np.argmax(pred_logits, axis=-1)
        pred_str = processor.batch_decode(pred_ids)  # CTC grouping for predictions

        label_ids = pred.label_ids
        label_str = [decode_labels_no_collapse(row, processor) for row in label_ids]

        wer_diac = float(jiwer.wer(label_str, pred_str))
        cer_diac = float(jiwer.cer(label_str, pred_str))

        label_plain = [strip_diacritics(s) for s in label_str]
        pred_plain = [strip_diacritics(s) for s in pred_str]
        wer_plain = float(jiwer.wer(label_plain, pred_plain))
        cer_plain = float(jiwer.cer(label_plain, pred_plain))

        return {"wer": wer_diac, "cer": cer_diac, "wer_plain": wer_plain, "cer_plain": cer_plain}

    return compute
