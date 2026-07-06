"""Corrector tests: pure logic (no model) + integration gated on a trained model.

Risk #2: the alignment/correction logic. The pure tests cover target prep,
word aggregation, and status classification without needing a trained model.
The integration test exercises the full path with whatever model is present
(e.g. the local smoke checkpoint).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quran_asr.alignment.corrector import Corrector
from quran_asr.alignment.forced_align import TokenBoundary, _prepare_targets
from quran_asr.alignment.postprocess import _geomean, tokens_to_words
from quran_asr.data_pipeline.normalize import normalize
from quran_asr.tokenizer.build_vocab import build_vocab_dict, save_vocab
from quran_asr.tokenizer.processor import build_processor

TEXTS = [
    "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ",
    "قُلْ هُوَ ٱللَّهُ أَحَدٌ",
]


@pytest.fixture(scope="module")
def processor(tmp_path_factory):
    d = tmp_path_factory.mktemp("vocab")
    vocab = build_vocab_dict(TEXTS)
    save_vocab(vocab, d / "vocab.json")
    return build_processor(d / "vocab.json")


def test_prepare_targets_drops_blanks_only():
    # torchaudio handles consecutive duplicates itself; we only remove blanks.
    ids = [5, 5, 0, 9, 9, 3]
    out = _prepare_targets(ids, blank_id=0)
    assert out == [5, 5, 9, 9, 3]


def test_geomean():
    import math

    assert _geomean([math.log(0.5), math.log(0.5)]) == pytest.approx(0.5)
    assert _geomean([]) == 0.0


def test_classify_thresholds():
    assert Corrector._classify(0.9) == "correct"
    assert Corrector._classify(0.3) == "low_confidence"
    assert Corrector._classify(0.02) == "skipped"


def test_tokens_to_words(processor):
    norm = normalize("قُلْ هُوَ ٱللَّهُ")
    ids = processor.tokenizer(norm).input_ids
    frame = 0.03
    boundaries = [
        TokenBoundary(token_id=i, start=k * frame, end=(k + 1) * frame, score=-0.4)
        for k, i in enumerate(ids)
    ]
    words = tokens_to_words(boundaries, processor)
    # round-trip: words joined by space reconstruct the normalized text
    assert " ".join(w.text for w in words) == norm
    for w in words:
        assert 0.0 <= w.confidence <= 1.0
        assert w.start <= w.end


# ---------------------------------------------------------------------------
# Integration — needs a trained model saved by `scripts/train.py`.
# ---------------------------------------------------------------------------
SMOKE_MODEL = Path("data/artifacts/checkpoints_smoke/final")
AUDIO = Path("data/raw/audio/Husary_128kbps_Mujawwad/001001.wav")


@pytest.mark.skipif(
    not (SMOKE_MODEL.exists() and AUDIO.exists()),
    reason="needs a trained model (run scripts/train.py --max-steps 2) + downloaded audio",
)
def test_corrector_end_to_end():
    import soundfile as sf

    from quran_asr.alignment.corrector import load_corrector

    audio, sr = sf.read(str(AUDIO))
    if audio.ndim > 1:
        audio = audio[:, 0]
    corrector = load_corrector("data/artifacts/checkpoints_smoke")
    results = corrector.correct(audio.tolist(), sr,
                                "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ")
    assert len(results) == 4  # basmala = 4 words
    for r in results:
        assert r.status in {"correct", "low_confidence", "skipped", "extra"}
        assert 0.0 <= r.confidence <= 1.0
        assert 0.0 <= r.start <= r.end
