"""Tokenizer/vocab tests. The critical property: each normalized character maps
1:1 to a token (no CTC collapse that would merge doubled letters like the ل in
ٱللَّهِ). We verify via ``id_to_token`` per id, not via CTC-collapsing decode."""

from __future__ import annotations

import os

import pytest

from quran_asr.data_pipeline.normalize import normalize
from quran_asr.tokenizer.build_vocab import (
    PAD_TOKEN,
    UNK_TOKEN,
    WORD_DELIMITER,
    build_vocab_dict,
    save_vocab,
)
from quran_asr.tokenizer.processor import build_processor

# Verbatim from quran.com Uthmani.
FATIHA_1 = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"  # has ٱللَّهِ (doubled ل + shadda)
FATIHA_7 = "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ"
IKHLAS = [
    "قُلْ هُوَ ٱللَّهُ أَحَدٌ",
    "ٱللَّهُ ٱلصَّمَدُ",
    "لَمْ يَلِدْ وَلَمْ يُولَدْ",
    "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ",  # ۥ ۢ stripped by normalize
]
ALL_TEXTS = [FATIHA_1, FATIHA_7, *IKHLAS]


def test_vocab_has_harakat_wasla_and_specials():
    vocab = build_vocab_dict(ALL_TEXTS)
    for ch in "َُِّْٰٓٱ":  # fatha, damma, shadda, sukun, sup-alef, maddah, wasla
        assert ch in vocab, f"missing token {ch!r}"
    assert WORD_DELIMITER in vocab
    assert UNK_TOKEN in vocab
    assert PAD_TOKEN in vocab


def test_vocab_size_reasonable():
    vocab = build_vocab_dict(ALL_TEXTS)
    # A small embedded sample yields a small vocab; the full-corpus size bound is
    # checked by the network-gated test below.
    assert 25 <= len(vocab) <= 70


@pytest.mark.parametrize("raw", ALL_TEXTS)
def test_processor_roundtrip_no_collapse(tmp_path, raw):
    vocab = build_vocab_dict(ALL_TEXTS)
    vocab_path = save_vocab(vocab, tmp_path / "vocab.json")
    tok = build_processor(vocab_path).tokenizer

    norm = normalize(raw)
    ids = tok(norm).input_ids
    # reconstruct token-by-token (NO CTC collapse) -> must equal normalized text
    tokens = tok.convert_ids_to_tokens(ids)
    recon = "".join(tokens).replace(WORD_DELIMITER, " ")
    assert recon == norm, f"round-trip failed:\n  recon={recon!r}\n  norm ={norm!r}"
    assert UNK_TOKEN not in set(tokens), "an [UNK] leaked in"


def test_doubled_letter_preserved(tmp_path):
    # ٱللَّهِ contains two consecutive ل (with shadda) — must NOT collapse to one.
    vocab = build_vocab_dict(ALL_TEXTS)
    vocab_path = save_vocab(vocab, tmp_path / "vocab.json")
    tok = build_processor(vocab_path).tokenizer
    norm = normalize("ٱللَّهِ")
    ids = tok(norm).input_ids
    tokens = tok.convert_ids_to_tokens(ids)
    # two ل tokens survive consecutively
    assert "ل" in tokens
    assert tokens.count("ل") >= 2


# ---------------------------------------------------------------------------
# Full-corpus vocab — network-gated.
# ---------------------------------------------------------------------------
_RUN_NETWORK = bool(os.environ.get("RUN_NETWORK_TESTS"))
network = pytest.mark.skipif(not _RUN_NETWORK, reason="set RUN_NETWORK_TESTS=1 to run")


@network
def test_vocab_from_full_corpus(tmp_path):
    from quran_asr.data_pipeline.fetch_text import fetch_uthmani

    m = fetch_uthmani(tmp_path / "q.json")
    vocab = build_vocab_dict(list(m.values()))
    assert 45 <= len(vocab) <= 70
    for ch in "َُِّْٰٓٱًٌٍٔ":
        assert ch in vocab
