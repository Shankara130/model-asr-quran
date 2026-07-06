"""Wav2Vec2Processor factory for the diacritics-aware CTC tokenizer.

Contract: text fed to the tokenizer MUST be normalized first (letters +
pronounced harakat only; spaces are word delimiters). The training preprocessing
map therefore does ``normalize(text) -> tokenizer``.
"""

from __future__ import annotations

from pathlib import Path

from transformers import Wav2Vec2CTCTokenizer, Wav2Vec2FeatureExtractor, Wav2Vec2Processor

from .build_vocab import PAD_TOKEN, UNK_TOKEN, WORD_DELIMITER


def build_processor(vocab_path: str | Path, sampling_rate: int = 16000) -> Wav2Vec2Processor:
    """Build a processor from a ``vocab.json`` (and its sibling config files)."""
    vocab_path = Path(vocab_path)
    # The constructor wants the vocab.json *file*; accept either a file or a dir.
    vocab_file = vocab_path / "vocab.json" if vocab_path.is_dir() else vocab_path
    tokenizer = Wav2Vec2CTCTokenizer(
        str(vocab_file),
        unk_token=UNK_TOKEN,
        pad_token=PAD_TOKEN,
        word_delimiter_token=WORD_DELIMITER,
    )
    feature_extractor = Wav2Vec2FeatureExtractor(
        feature_size=1,
        sampling_rate=sampling_rate,
        padding_value=0.0,
        do_normalize=True,
    )
    return Wav2Vec2Processor(feature_extractor=feature_extractor, tokenizer=tokenizer)
