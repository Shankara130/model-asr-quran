"""CLI: run the Corrector on one audio file + a reference ayah.

Example:
    uv run python scripts/correct.py --model-dir data/artifacts/checkpoints \\
        --audio data/raw/audio/Husary_128kbps_Mujawwad/001001.wav \\
        --text "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"
"""

from __future__ import annotations

import argparse

import soundfile as sf

from quran_asr.alignment.corrector import load_corrector


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--text", required=True, help="reference ayah text (diacritized)")
    ap.add_argument("--model-dir", default="data/artifacts/checkpoints/final")
    ap.add_argument("--device", default=None)
    args = ap.parse_args(argv)

    audio, sr = sf.read(args.audio)
    if audio.ndim > 1:
        audio = audio[:, 0]

    corrector = load_corrector(args.model_dir, device=args.device)
    results = corrector.correct(audio.tolist(), sr, args.text)

    print(f"{'#':>3}  {'status':<13}{'conf':>5}  {'start':>6}-{'end':<6}  word")
    for r in results:
        print(f"{r.index:>3}  {r.status:<13}{r.confidence:>5.2f}  "
              f"{r.start:>6.2f}-{r.end:<6.2f}  {r.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
