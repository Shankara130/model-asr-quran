"""CLI: build the diacritics-aware CTC vocab.json from the dataset (or corpus).

Example:
    uv run python scripts/build_vocab.py --config configs/tiny.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quran_asr.config import Config
from quran_asr.tokenizer.build_vocab import build_vocab_dict, save_vocab


def load_texts(cfg: Config) -> tuple[list[str], str]:
    """Prefer the built dataset's train+val text; fall back to the full corpus."""
    processed = Path(cfg.data.processed_dir)
    if (processed / "dataset_dict.json").exists():
        from datasets import load_from_disk

        dd = load_from_disk(processed)
        texts: list[str] = []
        for split in ("train", "validation"):  # never let test chars drive the vocab
            if split in dd:
                texts.extend(dd[split]["text"])
        return texts, "dataset(train+validation)"
    from quran_asr.data_pipeline.fetch_text import load_uthmani

    return list(load_uthmani(cfg.data.text_path).values()), "full quran corpus"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/tiny.yaml")
    ap.add_argument("--min-freq", type=int, default=1)
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    texts, source = load_texts(cfg)
    vocab = build_vocab_dict(texts, min_freq=args.min_freq)
    out = save_vocab(vocab, cfg.model.vocab_path)

    print(f"[vocab] {len(vocab)} tokens from {source} ({len(texts)} texts) -> {out}",
          file=sys.stderr)
    print(json.dumps(vocab, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
