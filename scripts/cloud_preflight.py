"""Cloud pre-flight checks: GPU, ffmpeg, deps, HF token, disk space.

Run this as the first step on Colab/Kaggle before the long training run.
Exits non-zero if any hard requirement is missing."""

from __future__ import annotations

import importlib
import os
import shutil

_checks: list[tuple[str, str, str]] = []


def _add(status: str, name: str, detail: str = "") -> None:
    _checks.append((status, name, detail))


def main() -> int:
    # GPU
    try:
        import torch

        if torch.cuda.is_available():
            _add("OK  ", "CUDA GPU", torch.cuda.get_device_name(0))
        else:
            _add("FAIL", "CUDA GPU", "no CUDA — switch runtime to GPU (T4/P100)")
    except Exception as exc:  # noqa: BLE001
        _add("FAIL", "CUDA GPU", str(exc)[:80])

    # ffmpeg
    if shutil.which("ffmpeg"):
        _add("OK  ", "ffmpeg", shutil.which("ffmpeg"))
    else:
        _add("FAIL", "ffmpeg", "install: apt-get install -y ffmpeg")

    # deps
    for mod in [
        "accelerate",
        "torch",
        "torchaudio",
        "transformers",
        "datasets",
        "evaluate",
        "jiwer",
        "soundfile",
        "librosa",
        "huggingface_hub",
        "yaml",
        "requests",
        "tqdm",
    ]:
        try:
            importlib.import_module(mod)
            _add("OK  ", f"dep {mod}")
        except Exception as exc:  # noqa: BLE001
            _add("FAIL", f"dep {mod}", str(exc)[:80])

    # HF token (only needed to push to Hub)
    from huggingface_hub import get_token

    token = get_token() or os.environ.get("HF_TOKEN")
    if token:
        _add("OK  ", "HF token", "present (can push to Hub)")
    else:
        _add("WARN", "HF token", "none — set logging.hub_repo=null or run notebook_login()")

    # disk (need ~15-20 GB for 2 reciters audio + checkpoints)
    try:
        disk_path = "/content" if os.path.exists("/content") else "/"
        st = os.statvfs(disk_path)
        gb = st.f_bavail * st.f_frsize / 1e9
        _add("OK  " if gb > 20 else "WARN", "disk free",
             f"{gb:.1f} GB free on {disk_path} (need ~15-20 GB)")
    except Exception as exc:  # noqa: BLE001
        _add("WARN", "disk free", str(exc)[:80])

    print("\n=== cloud pre-flight ===")
    for status, name, detail in _checks:
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    n_fail = sum(1 for s, _, _ in _checks if s.strip() == "FAIL")
    print(f"\n{n_fail} hard failure(s). Fix FAIL items before training.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
