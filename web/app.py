"""Flask web UI for Quran ASR inference with selectable models.

Run:
    uv sync
    uv run python web/app.py

Open:
    http://127.0.0.1:5000

The FastConformer option requires NVIDIA NeMo:
    uv pip install "nemo_toolkit[asr]"
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch
from flask import Flask, render_template, request
from huggingface_hub import snapshot_download
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from quran_asr.alignment.corrector import Corrector, make_model_normalizer
from quran_asr.audio_io import load_audio
from quran_asr.data_pipeline.fetch_text import load_uthmani
from quran_asr.data_pipeline.normalize import strip_diacritics

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / ".cache" / "hf"
CACHE_TORCH_DIR = PROJECT_ROOT / ".cache" / "torch"
CACHE_NEMO_DIR = CACHE_TORCH_DIR / "NeMo"
CACHE_MPL_DIR = PROJECT_ROOT / ".cache" / "matplotlib"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_NEMO_DIR.mkdir(parents=True, exist_ok=True)
CACHE_MPL_DIR.mkdir(parents=True, exist_ok=True)

HOME_NEMO_DIR = Path.home() / ".cache" / "torch" / "NeMo"
existing_nemo_dirs = sorted(p for p in HOME_NEMO_DIR.glob("NeMo_*") if p.is_dir())
if existing_nemo_dirs:
    CACHE_NEMO_DIR = existing_nemo_dirs[-1]

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("HF_HOME", str(CACHE_DIR))
os.environ.setdefault("HF_HUB_CACHE", str(CACHE_DIR / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(CACHE_DIR / "transformers"))
os.environ.setdefault("NEMO_CACHE_DIR", str(CACHE_NEMO_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_MPL_DIR))

TEXT_PATH = os.environ.get("QURAN_TEXT", str(PROJECT_ROOT / "data/raw/text/quran_uthmani.json"))

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)

MODEL_CHOICES: dict[str, dict[str, str]] = {
    "rabah2026": {
        "label": "rabah2026 wav2vec2 Quran",
        "backend": "transformers",
        "model_id": "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final",
        "note": "Transformers CTC, support word-level corrector.",
    },
    "fastconformer-quran": {
        "label": "mohammed FastConformer Quran",
        "backend": "nemo",
        "model_id": "mohammed/fastconformer-quran-ar",
        "note": "NeMo FastConformer, high-accuracy ASR, no word corrector in this UI.",
    },
}
DEFAULT_MODEL_KEY = os.environ.get("ASR_MODEL_KEY", "rabah2026")
if DEFAULT_MODEL_KEY not in MODEL_CHOICES:
    DEFAULT_MODEL_KEY = "rabah2026"

_loaded_models: dict[str, dict[str, Any]] = {}
_text = load_uthmani(TEXT_PATH)
_surahs = sorted({key[0] for key in _text})

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def load_selected_model(model_key: str) -> dict[str, Any]:
    if model_key not in MODEL_CHOICES:
        raise ValueError(f"Unknown model: {model_key}")
    if model_key in _loaded_models:
        return _loaded_models[model_key]

    choice = MODEL_CHOICES[model_key]
    backend = choice["backend"]
    model_id = choice["model_id"]
    print(f"Loading ASR model: {model_id} ({backend})")
    print(f"Device: {DEVICE}")

    if backend == "transformers":
        processor = Wav2Vec2Processor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id).to(DEVICE).eval()
        loaded = {
            "backend": backend,
            "model": model,
            "processor": processor,
            "corrector": Corrector(
                model,
                processor,
                normalizer=make_model_normalizer(processor),
                device=DEVICE,
            ),
        }
    elif backend == "nemo":
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise RuntimeError(
                "Model FastConformer butuh NeMo. Install dulu: "
                'uv pip install "nemo_toolkit[asr]"'
            ) from exc

        nemo_cache_dir = CACHE_DIR / "nemo" / model_key
        nemo_cache_dir.mkdir(parents=True, exist_ok=True)
        local_snapshot = snapshot_download(
            repo_id=model_id,
            local_dir=str(nemo_cache_dir),
            local_dir_use_symlinks=False,
            allow_patterns=["*.nemo", "*.yaml", "*.yml", "*.json", "*.txt"],
        )
        nemo_files = sorted(Path(local_snapshot).rglob("*.nemo"))
        if not nemo_files:
            raise RuntimeError(
                f"Repo HF {model_id} tidak berisi file .nemo yang bisa di-restore. "
                "Pakai model Transformers, atau pastikan repo menyediakan artefak .nemo."
            )

        model = nemo_asr.models.EncDecHybridRNNTCTCBPEModel.restore_from(
            restore_path=str(nemo_files[0]),
            map_location=torch.device(DEVICE),
        )
        model.change_decoding_strategy(decoder_type="ctc", verbose=False)
        model = model.to(DEVICE).eval()
        loaded = {"backend": backend, "model": model}
    else:
        raise ValueError(f"Unsupported backend: {backend}")

    _loaded_models[model_key] = loaded
    return loaded


def greedy_asr_transformers(loaded: dict[str, Any], audio: list[float], sample_rate: int) -> str:
    processor = loaded["processor"]
    model = loaded["model"]
    inputs = processor(audio, sampling_rate=sample_rate, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(DEVICE)).logits
    pred_ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(pred_ids)[0]


def prepare_audio_for_inference(audio: list[float], sample_rate: int) -> tuple[list[float], int]:
    arr = np.asarray(audio, dtype=np.float32)
    if arr.size == 0:
        return [], sample_rate

    import librosa

    trimmed, _ = librosa.effects.trim(arr, top_db=35)
    if trimmed.size >= int(sample_rate * 0.75):
        arr = trimmed

    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0:
        arr = np.clip(arr / peak * 0.95, -1.0, 1.0)

    return arr.astype(np.float32).tolist(), sample_rate


def _nemo_text(result: Any) -> str:
    item = result[0] if isinstance(result, (list, tuple)) else result
    if hasattr(item, "text"):
        return str(item.text)
    if isinstance(item, dict) and "text" in item:
        return str(item["text"])
    if isinstance(item, tuple) and item:
        return _nemo_text(item[0])
    return str(item)


def transcribe(
    model_key: str,
    audio_path: str,
    audio: list[float],
    sample_rate: int,
    raw_audio: list[float] | None = None,
) -> str:
    loaded = load_selected_model(model_key)
    if loaded["backend"] == "transformers":
        return greedy_asr_transformers(loaded, audio, sample_rate)
    if loaded["backend"] == "nemo":
        import soundfile as sf

        normalized_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                normalized_path = tmp.name
            sf.write(normalized_path, audio, sample_rate)
            result = loaded["model"].transcribe([normalized_path], batch_size=1, verbose=False)
            text = _nemo_text(result).strip()
            if text:
                return text

            if raw_audio is not None and raw_audio != audio:
                raw_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as raw_tmp:
                        raw_path = raw_tmp.name
                    sf.write(raw_path, raw_audio, sample_rate)
                    result = loaded["model"].transcribe([raw_path], batch_size=1, verbose=False)
                    return _nemo_text(result).strip()
                finally:
                    if raw_path:
                        os.unlink(raw_path)
        finally:
            if normalized_path:
                os.unlink(normalized_path)
    raise ValueError(f"Unsupported backend: {loaded['backend']}")


def maybe_correct_words(
    model_key: str,
    audio: list[float],
    sample_rate: int,
    reference: str,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    loaded = load_selected_model(model_key)
    if loaded["backend"] != "transformers":
        return None, "Word-level corrector belum tersedia untuk backend NeMo."

    try:
        words = loaded["corrector"].correct(audio, sample_rate, reference)
        return [
            {
                "index": word.index,
                "text": word.text,
                "status": word.status,
                "confidence": round(word.confidence, 2),
                "start": round(word.start, 2),
                "end": round(word.end, 2),
            }
            for word in words
        ], None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def wer_cer(reference: str, hypothesis: str) -> dict[str, float]:
    import jiwer

    ref_plain = strip_diacritics(reference)
    hyp_plain = strip_diacritics(hypothesis)
    return {
        "wer": float(jiwer.wer(reference, hypothesis)),
        "cer": float(jiwer.cer(reference, hypothesis)),
        "wer_plain": float(jiwer.wer(ref_plain, hyp_plain)),
        "cer_plain": float(jiwer.cer(ref_plain, hyp_plain)),
    }


def render(result: dict[str, Any] | None = None, selected_model: str | None = None):
    selected = selected_model or DEFAULT_MODEL_KEY
    model = MODEL_CHOICES[selected]
    return render_template(
        "index.html",
        surahs=_surahs,
        model_choices=MODEL_CHOICES,
        selected_model=selected,
        model=model,
        device=DEVICE,
        result=result,
    )


@app.route("/")
def index():
    return render()


@app.route("/infer", methods=["POST"])
def infer():
    model_key = request.form.get("model_key") or DEFAULT_MODEL_KEY
    if model_key not in MODEL_CHOICES:
        model_key = DEFAULT_MODEL_KEY

    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return render(
            selected_model=model_key,
            result={"error": "Upload audio atau rekam audio dulu.", "model_key": model_key},
        )

    reference = (request.form.get("reference") or "").strip()
    surah = request.form.get("surah", type=int)
    ayah = request.form.get("ayah", type=int)
    if not reference and surah and ayah:
        reference = _text.get((surah, ayah), "")

    suffix = Path(audio_file.filename).suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        raw_audio, sample_rate = load_audio(tmp_path)
        audio, sample_rate = prepare_audio_for_inference(raw_audio, sample_rate)
        raw_arr = np.asarray(raw_audio, dtype=np.float32)
        proc_arr = np.asarray(audio, dtype=np.float32)
        raw_peak = float(np.max(np.abs(raw_arr))) if raw_arr.size else 0.0
        proc_peak = float(np.max(np.abs(proc_arr))) if proc_arr.size else 0.0
        raw_rms = float(np.sqrt(np.mean(np.square(raw_arr)))) if raw_arr.size else 0.0
        proc_rms = float(np.sqrt(np.mean(np.square(proc_arr)))) if proc_arr.size else 0.0
        asr = transcribe(model_key, tmp_path, audio, sample_rate, raw_audio=raw_audio)
        asr = (asr or "").strip()
        print(
            f"[ASR] model={model_key} sample_rate={sample_rate} "
            f"audio_sec={len(audio) / sample_rate:.2f} "
            f"raw_peak={raw_peak:.3f} raw_rms={raw_rms:.3f} "
            f"proc_peak={proc_peak:.3f} proc_rms={proc_rms:.3f} "
            f"asr_len={len(asr)} asr={asr!r}"
        )
    except Exception as exc:  # noqa: BLE001
        return render(
            selected_model=model_key,
            result={
                "error": str(exc),
                "model_key": model_key,
                "ref": reference,
                "surah": surah,
                "ayah": ayah,
            },
        )
    finally:
        if tmp_path:
            os.unlink(tmp_path)

    result: dict[str, Any] = {
        "asr": asr,
        "asr_empty": not bool(asr),
        "ref": reference,
        "surah": surah,
        "ayah": ayah,
        "metrics": None,
        "words": None,
        "word_error": None,
        "error": None,
        "model_key": model_key,
    }

    if reference:
        result["metrics"] = wer_cer(reference, asr)
        words, word_error = maybe_correct_words(model_key, audio, sample_rate, reference)
        result["words"] = words
        result["word_error"] = word_error

    return render(selected_model=model_key, result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
