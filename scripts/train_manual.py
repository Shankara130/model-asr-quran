"""CLI: train wav2vec2 CTC with the manual low-VRAM loop.

Example:
    uv run python scripts/train_manual.py --config configs/local_3050.yaml
"""

from __future__ import annotations

import argparse

from quran_asr.config import Config
from quran_asr.training.manual_train import train_manual


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/local_3050.yaml")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    result = train_manual(
        cfg,
        output_dir=args.output_dir,
        resume=not args.no_resume,
        max_epochs=args.epochs,
    )
    print(f"Best {result.best_metric}: {result.best_score}")
    print(f"Best checkpoint: {result.best_dir}")
    print(f"Final checkpoint: {result.final_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
