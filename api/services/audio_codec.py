from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from api.core.errors import ApiError
from api.settings import settings

FFMPEG_BIN = shutil.which("ffmpeg")


def decode_any(src: Path) -> np.ndarray:
    """Decode any ffmpeg-supported audio to 16 kHz mono float32 PCM."""
    if FFMPEG_BIN is None:
        raise ApiError(
            "audio_unprocessable",
            "ffmpeg tidak tersedia di server.",
            details={"missing": "ffmpeg"},
        )
    if not src.exists():
        raise ApiError("audio_unprocessable", "File audio tidak ditemukan.")

    cmd = [
        FFMPEG_BIN,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "f32le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)  # noqa: S603 - trusted bin + args
    if proc.returncode != 0 or not proc.stdout:
        raise ApiError(
            "audio_unprocessable",
            "Audio tidak dapat didekode.",
            details={"ffmpeg_returncode": proc.returncode},
        )

    samples = np.frombuffer(proc.stdout, dtype=np.float32)
    max_samples = settings.max_audio_duration_seconds * 16_000
    if samples.size > max_samples:
        raise ApiError(
            "audio_unprocessable",
            "Durasi audio melebihi batas maksimum.",
            details={"max_seconds": settings.max_audio_duration_seconds},
        )
    return samples
