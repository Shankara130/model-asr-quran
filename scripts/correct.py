"""CLI: run the Corrector on one audio file + a reference ayah.

Loads either a locally-trained model (--model-dir) or any HF Hub CTC model
(--hf-model), e.g. the pretrained ``rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final``.

Examples:
    # locally-trained model
    uv run python scripts/correct.py --model-dir data/artifacts/checkpoints/final \\
        --audio data/raw/audio/Husary_128kbps_Mujawwad/001001.wav \\
        --text "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"

    # pretrained HF model (no training needed)
    uv run python scripts/correct.py \\
        --hf-model rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final \\
        --audio data/raw/audio/Husary_128kbps_Mujawwad/001001.wav \\
        --text "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ" --show-asr
"""

from __future__ import annotations

import argparse

from quran_asr.audio_io import load_audio


def _load_hf_corrector(hf_model: str, device: str | None):
    """Load any HF Hub Wav2Vec2ForCTC into a Corrector with a vocab-aware
    normalizer (drops chars the model can't encode, e.g. the hamza-above `ٕ`
    that rabah2026's vocab lacks)."""
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    from quran_asr.alignment.corrector import Corrector, make_model_normalizer

    model = Wav2Vec2ForCTC.from_pretrained(hf_model)
    processor = Wav2Vec2Processor.from_pretrained(hf_model)
    dev = device or (
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )
    return Corrector(model, processor, device=dev, normalizer=make_model_normalizer(processor))


def _free_asr(corrector, audio, sample_rate: int) -> str:
    """Greedy (argmax) transcription — sanity check of what the model 'hears'."""
    import torch

    inputs = corrector.processor(audio, sampling_rate=sample_rate, return_tensors="pt")
    with torch.no_grad():
        logits = corrector.model(inputs.input_values.to(corrector.device)).logits
    ids = torch.argmax(logits, dim=-1)
    return corrector.processor.batch_decode(ids)[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--text", required=True, help="reference ayah text (diacritized)")
    target = ap.add_mutually_exclusive_group()
    target.add_argument(
        "--model-dir", default=None, help="local trained model dir (with a final/ subfolder)"
    )
    target.add_argument(
        "--hf-model",
        default=None,
        help="HF Hub CTC model id, e.g. rabah2026/wav2vec2-...-quran-v_final",
    )
    ap.add_argument("--device", default=None)
    ap.add_argument(
        "--show-asr",
        action="store_true",
        help="also print the model's greedy transcription for sanity",
    )
    args = ap.parse_args(argv)

    audio, sr = load_audio(args.audio)

    if args.hf_model:
        corrector = _load_hf_corrector(args.hf_model, args.device)
        print(f"[correct] HF model: {args.hf_model} on {corrector.device}", flush=True)
    else:
        from quran_asr.alignment.corrector import load_corrector

        corrector = load_corrector(
            args.model_dir or "data/artifacts/checkpoints/final", device=args.device
        )

    if args.show_asr:
        print(f"[asr]  {_free_asr(corrector, audio, sr)}", flush=True)

    results = corrector.correct(audio, sr, args.text)

    print(f"{'#':>3}  {'status':<13}{'conf':>5}  {'start':>6}-{'end':<6}  word")
    for r in results:
        print(
            f"{r.index:>3}  {r.status:<13}{r.confidence:>5.2f}  "
            f"{r.start:>6.2f}-{r.end:<6.2f}  {r.text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
