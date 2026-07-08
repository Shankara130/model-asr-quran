# Live ASR Inference Implementation Plan

**For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans implement plan task-by-task.

**Goal:** Build a separate inference CLI that records or loads audio, resolves Quran Uthmani references by surah/ayah, and reports transcript, correction hints, WER/CER, confidence, blank rate, and latency.

**Architecture:** Keep reference lookup independent from model inference so it can be tested without loading transformers. Put reusable ASR decode and metric helpers in `quran_asr/inference_live.py`; keep microphone and CLI concerns in `scripts/live_infer_asr.py`.

**Tech Stack:** Python, PyTorch, Transformers CTC models, jiwer, soundfile/librosa for file audio, optional sounddevice for microphone.

---

### Task 1: Uthmani Reference Lookup

**Files:**
- Create: `quran_asr/reference.py`
- Test: `tests/test_reference.py`

- [ ] Add `resolve_reference(text_path, surah, ayah, reference)` that returns manual reference if supplied, otherwise loads `data/raw/text/quran_uthmani.json` through `load_uthmani`.
- [ ] Raise a clear `ValueError` if only one of `surah` or `ayah` is supplied.
- [ ] Add tests for manual reference, valid Uthmani lookup, and incomplete surah/ayah arguments.

### Task 2: Reusable Live Inference Helpers

**Files:**
- Create: `quran_asr/inference_live.py`
- Test: `tests/test_inference_live.py`

- [ ] Add `compute_text_metrics(reference, hypothesis)` returning WER/CER with and without harakat.
- [ ] Add `format_correction(reference, hypothesis)` using a compact word-level diff.
- [ ] Add `decode_audio(model, processor, audio, sample_rate, device)` that returns prediction, latency, confidence proxy, blank rate, and top tokens.
- [ ] Keep heavy imports usable, but tests should only cover pure metric/diff helpers.

### Task 3: CLI Script

**Files:**
- Create: `scripts/live_infer_asr.py`
- Create: `docs/LIVE_INFERENCE.md`

- [ ] Support `--model`, `--audio`, `--live`, `--record-seconds`, `--chunk-seconds`, `--surah`, `--ayah`, `--reference`, `--text-path`, and `--device`.
- [ ] Load model with `AutoProcessor` and `AutoModelForCTC`.
- [ ] For `--audio`, decode one file and print transcript, latency, confidence, blank rate, and metrics if reference exists.
- [ ] For `--live`, record chunks from mic using optional `sounddevice`, print each chunk result, and stop on Ctrl+C.
- [ ] Document examples for HF model and local checkpoint.

### Task 4: Verification

**Files:**
- Modify: `tests/test_smoke.py` only if needed.

- [ ] Run `python -m py_compile quran_asr/reference.py quran_asr/inference_live.py scripts/live_infer_asr.py`.
- [ ] Run `uv run ruff check quran_asr/reference.py quran_asr/inference_live.py scripts/live_infer_asr.py tests/test_reference.py tests/test_inference_live.py`.
- [ ] Run targeted tests for new helpers.
- [ ] Run full pytest.
