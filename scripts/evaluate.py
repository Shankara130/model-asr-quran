"""CLI: evaluate a trained model (WER/CER + per-reciter + word-level rates).

Example:
    uv run python scripts/evaluate.py --config configs/tiny.yaml \\
        --model-dir data/artifacts/checkpoints
"""

from __future__ import annotations

import argparse
import json
import sys

from quran_asr.config import Config
from quran_asr.evaluation.evaluate import evaluate, save_results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/tiny.yaml")
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--split", default="test")
    ap.add_argument("--corrector-sample", type=int, default=50)
    ap.add_argument("--out", default="data/artifacts/metrics.json")
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    results = evaluate(cfg, model_dir=args.model_dir, split=args.split,
                       corrector_sample=args.corrector_sample)
    out = save_results(results, args.out)
    print(json.dumps(results, ensure_ascii=False, indent=2), file=sys.stderr)
    print(f"[eval] written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
