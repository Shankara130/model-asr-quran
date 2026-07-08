"""Live/file ASR inference for Quran recitation models.

Examples:
    python scripts/live_infer_asr.py --audio sample.wav --surah 94 --ayah 1
    python scripts/live_infer_asr.py --live --surah 94 --ayah 1
    python scripts/live_infer_asr.py --model TBOGamer22/wav2vec2-quran-phonetics --live
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCTC, AutoProcessor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quran_asr.audio_io import load_audio  # noqa: E402
from quran_asr.inference_live import (  # noqa: E402
    compute_text_metrics,
    decode_audio,
    format_correction,
)
from quran_asr.reference import resolve_reference  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.audio and not args.live and args.record_seconds <= 0:
        raise SystemExit("provide --audio, --live, or --record-seconds")

    device = _select_device(args.device)
    reference = resolve_reference(args.text_path, args.surah, args.ayah, args.reference)
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForCTC.from_pretrained(args.model).to(device).eval()

    print("model:", args.model)
    print("device:", device)
    if reference:
        print("reference:", reference)

    if args.audio:
        audio, sr = load_audio(args.audio, args.sample_rate)
        _decode_and_print(model, processor, audio, sr, device, reference, "file")
        return 0

    if args.record_seconds > 0:
        audio = _record_audio(args.record_seconds, args.sample_rate)
        _decode_and_print(model, processor, audio, args.sample_rate, device, reference, "record")
        return 0

    _run_live(model, processor, args.sample_rate, args.chunk_seconds, device, reference)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="TBOGamer22/wav2vec2-quran-phonetics",
        help="HF model id or local checkpoint directory.",
    )
    parser.add_argument("--audio", default=None, help="Audio file to decode once.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Continuously record microphone chunks.",
    )
    parser.add_argument(
        "--record-seconds",
        type=float,
        default=0.0,
        help="Record one microphone sample for N seconds, then decode once.",
    )
    parser.add_argument("--chunk-seconds", type=float, default=4.0)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--surah", type=int, default=None)
    parser.add_argument("--ayah", type=int, default=None)
    parser.add_argument("--reference", default=None, help="Manual reference text override.")
    parser.add_argument("--text-path", default="data/raw/text/quran_uthmani.json")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    return parser.parse_args(argv)


def _select_device(requested: str) -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise SystemExit("CUDA requested but torch.cuda.is_available() is false")
        return torch.device("cuda")
    if requested == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _run_live(
    model,
    processor,
    sample_rate: int,
    chunk_seconds: float,
    device: torch.device,
    reference: str | None,
) -> None:
    print("live recording; press Ctrl+C to stop")
    chunk_index = 1
    try:
        while True:
            audio = _record_audio(chunk_seconds, sample_rate)
            _decode_and_print(
                model,
                processor,
                audio,
                sample_rate,
                device,
                reference,
                f"chunk {chunk_index}",
            )
            chunk_index += 1
    except KeyboardInterrupt:
        print("\nstopped")


def _record_audio(seconds: float, sample_rate: int) -> list[float]:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit(
            "microphone recording needs sounddevice. Install it with: uv add sounddevice"
        ) from exc

    n_samples = int(seconds * sample_rate)
    print(f"recording {seconds:.1f}s...")
    started = time.perf_counter()
    audio = sd.rec(n_samples, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    elapsed = time.perf_counter() - started
    print(f"recorded in {elapsed:.2f}s")
    return audio.reshape(-1).tolist()


def _decode_and_print(
    model,
    processor,
    audio: list[float],
    sample_rate: int,
    device: torch.device,
    reference: str | None,
    label: str,
) -> None:
    result = decode_audio(model, processor, audio, sample_rate, device)
    duration = len(audio) / sample_rate

    print("\n" + "=" * 72)
    print(label)
    print(f"duration_sec: {duration:.2f}")
    print(f"latency_ms: {result.latency_ms:.1f}")
    print(f"confidence: {result.confidence:.4f}")
    print(f"non_blank_confidence: {result.non_blank_confidence:.4f}")
    print(f"blank_rate: {result.blank_rate:.1%}")
    print("pred:", repr(result.text))

    if reference:
        metrics = compute_text_metrics(reference, result.text)
        print("target:", reference)
        print(
            "metrics:",
            " ".join(
                f"{name}={value:.4f}"
                for name, value in metrics.items()
            ),
        )
        print("correction:", format_correction(reference, result.text))

    print("top_tokens:")
    for idx, token, prob in result.top_tokens:
        print(f"  {idx:>3} {token!r:<12} {prob:.6f}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
