"""CLI: train the wav2vec2 CTC model.

Examples:
    uv run python scripts/train.py --config configs/tiny.yaml --max-steps 2   # smoke
    uv run python scripts/train.py --config configs/base.yaml                 # cloud (full)
"""

from __future__ import annotations

import argparse

from quran_asr.config import Config
from quran_asr.training.train import train


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/tiny.yaml")
    ap.add_argument("--epochs", type=float, default=None, help="override config epochs")
    ap.add_argument("--max-steps", type=int, default=None, help="smoke test: cap training steps")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    train(cfg, epochs=args.epochs, max_steps=args.max_steps,
          output_dir=args.output_dir, resume=args.resume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
