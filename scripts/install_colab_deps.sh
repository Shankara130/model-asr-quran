#!/usr/bin/env bash
set -euo pipefail

python -m pip install -q -U pip

if python - <<'PY'
import torch
import torchaudio
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY
then
  echo "Using existing CUDA PyTorch:"
  python - <<'PY'
import torch
import torchaudio
print(f"  torch={torch.__version__} cuda={torch.version.cuda} device={torch.cuda.get_device_name(0)}")
print(f"  torchaudio={torchaudio.__version__}")
PY
else
  CUDA_TAG="${PYTORCH_CUDA:-cu121}"
  echo "Installing PyTorch CUDA wheels (${CUDA_TAG}). Set PYTORCH_CUDA=cu124/cu126 if your Colab image requires it."
  python -m pip install -q --upgrade torch torchaudio --index-url "https://download.pytorch.org/whl/${CUDA_TAG}"
fi

python -m pip install -q -r requirements-colab.txt
apt-get -qq update >/dev/null
apt-get -qq install -y ffmpeg >/dev/null

python - <<'PY'
import importlib
import shutil
import torch

mods = [
    "accelerate",
    "datasets",
    "evaluate",
    "jiwer",
    "librosa",
    "soundfile",
    "torch",
    "torchaudio",
    "transformers",
    "yaml",
]
missing = [mod for mod in mods if importlib.util.find_spec(mod) is None]
if missing:
    raise SystemExit(f"Missing deps after install: {missing}")
if not shutil.which("ffmpeg"):
    raise SystemExit("ffmpeg is missing")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available. In Colab: Runtime > Change runtime type > GPU, then rerun.")
print(f"CUDA ready: {torch.cuda.get_device_name(0)}")
PY
