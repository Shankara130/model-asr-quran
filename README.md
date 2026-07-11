# model-asr-quran

wav2vec2 **Quran recitation ASR** + **word/diacritics-level correction** model.
This is the **model phase** of a larger app (Flutter + Python + WebSocket); the
backend and mobile app land in later phases.

> Dokumentasi ini tersedia juga dalam [Bahasa Indonesia](README.id.md).

## What it does

1. **ASR** — transcribes Quranic recitation with **full diacritics (tashkeel)**.
2. **Correction** — because the reference text (the ayah) is always known, the
   core mechanism is **CTC forced alignment**, not free ASR. Each reference word
   is aligned to the audio and scored, producing a verdict:
   `correct` / `low_confidence` (suspect mispronunciation) / `skipped` (missed
   word) / `extra` (added word).

## Data

- **Audio**: [everyayah.com](https://everyayah.com) — verse-segmented MP3,
  `https://everyayah.com/data/<Reciter>/<SSSAAA>.mp3`.
- **Text**: fully-diacritized Uthmani text from the
  [quran.com API](https://api.quran.com/api/v4/quran/verses/uthmani). Text↔audio
  alignment is a trivial 1:1 map per (surah, ayah).

## Quickstart

```bash
make setup          # uv sync — create venv, install deps
make download       # fetch audio + diacritized text (configs/tiny.yaml by default)
make build          # assemble HF Dataset (data/processed)
make vocab          # build diacritics-aware CTC vocab.json
make test           # pytest
```

Training runs on **free cloud GPU** (Google Colab / Kaggle) via
`notebooks/01_colab_train.ipynb`, which calls the same `quran_asr.training.train`
entrypoint as the local `scripts/train.py`. The local `tiny.yaml` config is for
M1 sanity runs only.

### Training

```bash
# Cloud (Colab/Kaggle notebook does all of this): download -> build -> vocab -> train -> eval
# Local Apple Silicon sanity (tiny subset, wav2vec2-base):
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/train.py --config configs/tiny.yaml --max-steps 2
```

> Apple Silicon note: `ctc_loss` has no MPS kernel, so set
> `PYTORCH_ENABLE_MPS_FALLBACK=1` locally (the library sets this automatically on
> import). Real training is on cloud CUDA where it's native.

**Cross-speaker check**: once you have ≥2 reciters, switch `data.split.strategy`
to `by_reciter` and compare WER against `by_surah`. A large gap signals speaker
overfit — the model memorized one voice rather than generalizing.

```bash
uv run python scripts/evaluate.py --config configs/base.yaml --split test
uv run python scripts/correct.py --model-dir data/artifacts/checkpoints \
    --audio data/raw/audio/Husary_128kbps_Mujawwad/001001.wav \
    --text "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"
```

## Status (model phase)

M0 repo+env · M1 data pipeline · M2 tokenizer · M3 training · M4 aligner+corrector
· M5 evaluation — **all implemented and locally smoke-validated** (34 tests).
Next: a full cloud training run (M3 real), then the Python backend + WebSocket +
Flutter (separate phase). See the plan file for verification commands.

## Honest limitations

Forced alignment measures **how well the audio matches the expected token
sequence** — it does *not* cleanly separate "wrong harakat" from noise, reverb,
or tempo. Tajweed-grade correction needs phoneme-level modeling + Goodness-of-
Pronunciation (GOP) scoring, which is a **Phase 2** goal, out of scope here.

Realistic quality ceiling with this data + free-GPU budget:
`WER_plain ~5–10%`, `WER_diac ~15–30%` (harakat errors dominate). Good enough for
"did they recite the right words?", not yet for "was this tajweed correct?".

## Backend API (FastAPI)

The `api/` package wraps the ASR engine behind the **Sobat Ngaji** backend contract
(`BackendRequirements.md`): auth, profile, home, practice items/sessions, chunked +
simple audio upload, WebSocket realtime, evaluation, and insights. It is **separate**
from the Flask demo in `web/` (which stays intact) and **reuses `web/services/*`**
verbatim.

The app **boots without the ONNX model** — only the evaluation path loads it lazily.
All non-auth endpoints require `Authorization: Bearer <token>`; responses follow the
spec's standard error shape with `X-Request-Id`.

```bash
make backend-setup   # uv sync --extra backend (no sherpa_onnx / model needed)
make backend         # uvicorn on 127.0.0.1:8000  (python -m api)
make backend-test    # pytest api/tests
```

Dev auth is a stub: login as `alya@sobat.ngaji` with any password. To run real
evaluation, drop the model under `external/zipformer_p-quran/` and
`uv sync --extra asr`.

## Flask demo

The original single-page ASR tester (Flask + Flask-SocketIO) still runs separately:

```
python -m web.app
```

## License

Code: MIT. Audio © EveryAyah reciters; text from quran.com (Tanzil/Uthmani).
