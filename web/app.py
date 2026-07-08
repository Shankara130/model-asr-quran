"""Flask web UI for Quran ASR inference with the pretrained rabah2026 model.

No fine-tuning required: it loads `rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final`
once at startup and serves greedy transcription + (optional) word-level corrector
verdicts + WER/CER against a reference.

Run:
    uv add flask                      # one-time dependency
    uv run python web/app.py
Then open http://127.0.0.1:5000

Env overrides:
    ASR_MODEL   HF id or local checkpoint dir (default: rabah2026/...-quran-v_final)
    QURAN_TEXT  path to the diacritized quran.com JSON (default: data/raw/text/quran_uthmani.json)
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # MPS fallback for stray ops

import tempfile
from pathlib import Path

import torch
from flask import Flask, redirect, render_template, request, url_for
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from quran_asr.alignment.corrector import Corrector, make_model_normalizer
from quran_asr.audio_io import load_audio
from quran_asr.data_pipeline.fetch_text import load_uthmani
from quran_asr.data_pipeline.normalize import strip_diacritics

MODEL_ID = os.environ.get("ASR_MODEL", "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final")
TEXT_PATH = os.environ.get("QURAN_TEXT", "data/raw/text/quran_uthmani.json")

device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

# --- load model + reference text ONCE at import ---------------------------------
_processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
_model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID).to(device).eval()
_corrector = Corrector(_model, _processor, device=device, normalizer=make_model_normalizer(_processor))
_text = load_uthmani(TEXT_PATH)            # {(surah, ayah): diacritized text}
_surahs = sorted({k[0] for k in _text})    # [1..114]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload cap


def greedy_asr(audio: list[float], sr: int) -> str:
    inputs = _processor(audio, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = _model(inputs.input_values.to(device)).logits
    ids = torch.argmax(logits, dim=-1)
    return _processor.batch_decode(ids)[0]


def wer_cer(ref: str, hyp: str) -> dict[str, float]:
    import jiwer

    ref_p, hyp_p = strip_diacritics(ref), strip_diacritics(hyp)
    return {
        "wer": jiwer.wer(ref, hyp),
        "cer": jiwer.cer(ref, hyp),
        "wer_plain": jiwer.wer(ref_p, hyp_p),
        "cer_plain": jiwer.cer(ref_p, hyp_p),
    }


@app.route("/")
def index():
    return render_template("index.html", surahs=_surahs, model=MODEL_ID, device=device, result=None)


@app.route("/infer", methods=["POST"])
def infer():
    f = request.files.get("audio")
    if not f or not f.filename:
        return redirect(url_for("index"))

    ref = (request.form.get("reference") or "").strip()
    surah = request.form.get("surah", type=int)
    ayah = request.form.get("ayah", type=int)
    if not ref and surah and ayah:
        ref = _text.get((surah, ayah), "")

    # save upload to a temp file and decode (load_audio handles wav/mp3 via soundfile/librosa)
    suffix = Path(f.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name
    try:
        audio, sr = load_audio(tmp_path)
    finally:
        os.unlink(tmp_path)

    asr = greedy_asr(audio, sr)
    result: dict = {"asr": asr, "ref": ref, "surah": surah, "ayah": ayah,
                    "metrics": None, "words": None}
    if ref:
        result["metrics"] = wer_cer(ref, asr)
        try:
            words = _corrector.correct(audio, sr, ref)
            result["words"] = [
                {"index": w.index, "text": w.text, "status": w.status,
                 "confidence": round(w.confidence, 2), "start": round(w.start, 2),
                 "end": round(w.end, 2)}
                for w in words
            ]
        except Exception as exc:  # noqa: BLE001
            result["word_error"] = str(exc)
    return render_template("index.html", surahs=_surahs, model=MODEL_ID, device=device, result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
