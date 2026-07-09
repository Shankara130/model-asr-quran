"""Audio loading helper — decode any audio file to a mono float32 waveform.

We deliberately do NOT rely on the HuggingFace ``Audio`` feature (which in
datasets>=4 forces ``torchcodec``). torchcodec's load is fragile on cloud GPUs
(libnvrtc / torch-CUDA version mismatches). Reading with ``soundfile`` (with a
``librosa`` fallback for resampling / formats libsndfile can't open) is robust
everywhere: Mac, Colab, Kaggle, and the backend.
"""

from __future__ import annotations

from pathlib import Path


def load_audio(path: str | Path, target_sr: int = 16000) -> tuple[list[float], int]:
    """Return (mono float32 waveform, sample_rate). Resamples if needed."""
    import numpy as np

    try:
        import soundfile as sf

        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except Exception:
        import librosa

        data, sr = librosa.load(str(path), sr=target_sr, mono=True)

    if data.ndim > 1:
        data = data[:, 0]
    if sr != target_sr:
        import librosa

        data = librosa.resample(np.asarray(data), orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return data.tolist(), sr
