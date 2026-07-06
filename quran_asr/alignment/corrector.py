"""Word-level Corrector: align a known reference ayah to recited audio and
classify each word.

Status logic (forced alignment aligns *every* reference token to frames, so a
missing/inaudible word shows up as a very-low-confidence alignment rather than
an absence):

  * ``correct``        — confidence >= low_conf_threshold
  * ``low_confidence`` — below correct but >= skip_threshold (suspect mispron.)
  * ``skipped``        — below skip_threshold (likely not spoken)
  * ``extra``          — reserved; forced alignment cannot reliably surface added
                         words (it assigns all frames to reference tokens / blank).
                         Detecting added words needs the free-running ASR path
                         (documented Phase-2 addition).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import torch

from quran_asr.alignment.forced_align import align
from quran_asr.alignment.postprocess import tokens_to_words

WordStatus = Literal["correct", "low_confidence", "skipped", "extra"]


@dataclass
class WordResult:
    text: str
    start: float
    end: float
    confidence: float
    status: WordStatus
    index: int


class Corrector:
    def __init__(
        self,
        model: Any,
        processor: Any,
        device: str | torch.device | None = None,
        low_conf_threshold: float = 0.5,
        skip_threshold: float = 0.1,
    ):
        self.model = model
        self.processor = processor
        self.low_conf_threshold = low_conf_threshold
        self.skip_threshold = skip_threshold
        if device is not None:
            self.model.to(device)
        self.device = next(self.model.parameters()).device

    def correct(self, audio: list[float], sample_rate: int, ref_text: str) -> list[WordResult]:
        boundaries, _ = align(self.model, self.processor, audio, sample_rate, ref_text)
        words = tokens_to_words(boundaries, self.processor)
        return [
            WordResult(text=w.text, start=w.start, end=w.end, confidence=w.confidence,
                       status=self._classify(w.confidence, self.low_conf_threshold,
                                             self.skip_threshold),
                       index=w.index)
            for w in words
        ]

    @staticmethod
    def _classify(
        confidence: float, low_conf_threshold: float = 0.5, skip_threshold: float = 0.1,
    ) -> WordStatus:
        if confidence < skip_threshold:
            return "skipped"
        if confidence < low_conf_threshold:
            return "low_confidence"
        return "correct"


def load_corrector(
    model_dir: str | Path,
    device: str | torch.device | None = None,
    low_conf_threshold: float = 0.5,
    skip_threshold: float = 0.1,
) -> Corrector:
    """Load a trained model + processor saved by ``train()`` into ``<model_dir>/final``."""
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    root = Path(model_dir)
    final = root / "final" if (root / "final").exists() else root
    model = Wav2Vec2ForCTC.from_pretrained(str(final))
    processor = Wav2Vec2Processor.from_pretrained(str(final))
    return Corrector(model, processor, device=device,
                     low_conf_threshold=low_conf_threshold, skip_threshold=skip_threshold)
