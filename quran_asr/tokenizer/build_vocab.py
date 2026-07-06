"""Build a diacritics-aware CTC character vocabulary.

The vocabulary is derived from the *normalized* corpus (letters + pronounced
harakat kept; everything else stripped by :mod:`...normalize`). Tokens:

  * every surviving character (sorted by frequency desc, deterministic)
  * ``|``  — word delimiter (replaces space; HF Wav2Vec2 convention)
  * ``[UNK]``
  * ``[PAD]``  — also the CTC blank (see processor/model wiring)

CTC is permutation-invariant, so token order is cosmetic; we sort only for
readability. Expected size ~50–55 tokens.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from quran_asr.data_pipeline.normalize import DEFAULT_POLICY, NormalizePolicy, normalize

WORD_DELIMITER = "|"
UNK_TOKEN = "[UNK]"
PAD_TOKEN = "[PAD]"


def build_vocab_dict(
    texts,
    min_freq: int = 1,
    policy: NormalizePolicy = DEFAULT_POLICY,
) -> dict[str, int]:
    """Scan texts -> char freq -> ``{token: id}`` dict (specials last)."""
    counter: Counter[str] = Counter()
    for t in texts:
        for ch in normalize(t, policy):
            if ch == " ":
                continue  # space becomes the word-delimiter token
            counter[ch] += 1

    chars = [(ch, n) for ch, n in counter.items() if n >= min_freq]
    chars.sort(key=lambda cn: (-cn[1], cn[0]))  # freq desc, then codepoint

    vocab: dict[str, int] = {}
    for ch, _ in chars:
        vocab[ch] = len(vocab)
    vocab[WORD_DELIMITER] = len(vocab)
    vocab[UNK_TOKEN] = len(vocab)
    vocab[PAD_TOKEN] = len(vocab)
    return vocab


def save_vocab(vocab: dict[str, int], vocab_path: str | Path) -> Path:
    """Write vocab.json + tokenizer_config.json + special_tokens_map.json.

    ``vocab_path`` is the full path to ``vocab.json`` (siblings are written
    next to it)."""
    vocab_path = Path(vocab_path)
    vocab_path.parent.mkdir(parents=True, exist_ok=True)

    with vocab_path.open("w", encoding="utf-8") as fh:
        json.dump(vocab, fh, ensure_ascii=False, indent=1)

    special = {
        "unk_token": UNK_TOKEN,
        "pad_token": PAD_TOKEN,
        "word_delimiter_token": WORD_DELIMITER,
    }
    with (vocab_path.parent / "special_tokens_map.json").open("w", encoding="utf-8") as fh:
        json.dump(special, fh, ensure_ascii=False, indent=1)

    config = {**special, "do_lower_case": False, "tokenizer_class": "Wav2Vec2CTCTokenizer"}
    with (vocab_path.parent / "tokenizer_config.json").open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=1)

    return vocab_path
