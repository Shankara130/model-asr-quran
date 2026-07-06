"""CLI: download everyayah audio + diacritized text per config.

Examples:
    uv run python scripts/download.py --config configs/tiny.yaml
    uv run python scripts/download.py --reciter Husary_128kbps_Mujawwad --surahs 1,112
"""

from __future__ import annotations

import argparse
import sys

from quran_asr.config import Config
from quran_asr.data_pipeline.download_audio import download_audio, summarize
from quran_asr.data_pipeline.fetch_text import all_ayah_keys, fetch_uthmani


def ayah_keys_for(surahs: list[int] | str) -> list[tuple[int, int]]:
    keys = all_ayah_keys()
    if surahs in ("all", ["all"]):
        return keys
    allowed = set(surahs)
    return [k for k in keys if k[0] in allowed]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/tiny.yaml")
    ap.add_argument("--reciter", default=None, help="override config reciter list (single)")
    ap.add_argument("--surahs", default=None, help="comma list, e.g. 1,112,114")
    ap.add_argument("--max-workers", type=int, default=8)
    ap.add_argument("--qps", type=float, default=20.0)
    ap.add_argument("--no-convert", action="store_true", help="keep MP3, skip WAV")
    args = ap.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    reciters = [args.reciter] if args.reciter else list(cfg.data.reciters)
    surahs: list[int] | str
    if args.surahs:
        surahs = [int(x) for x in args.surahs.split(",") if x.strip()]
    else:
        surahs = cfg.data.surahs

    # make sure diacritized text is cached (1 request, ~1.6 MB)
    fetch_uthmani(cfg.data.text_path)
    print(f"[text] cache ready: {cfg.data.text_path}", file=sys.stderr)

    keys = ayah_keys_for(surahs)
    print(f"[audio] {len(keys)} ayat × {len(reciters)} reciter(s)", file=sys.stderr)

    for reciter in reciters:
        results = download_audio(
            reciter, keys, cfg.data.audio_dir,
            sample_rate=cfg.data.sample_rate,
            max_workers=args.max_workers,
            rate_limit_qps=args.qps,
            convert=not args.no_convert,
        )
        print(f"[{reciter}] {summarize(results)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
