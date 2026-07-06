"""CLI: assemble the HF DatasetDict from downloaded audio + text and save it.

Example:
    uv run python scripts/build.py --config configs/tiny.yaml
"""

from __future__ import annotations

import argparse
import sys

from quran_asr.config import Config
from quran_asr.data_pipeline.build_dataset import build_dataset


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/tiny.yaml")
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    dd = build_dataset(cfg)
    dd.save_to_disk(cfg.data.processed_dir)

    for name, split in dd.items():
        print(f"  {name}: {len(split)} rows", file=sys.stderr)
    print(f"[build] saved DatasetDict to {cfg.data.processed_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
