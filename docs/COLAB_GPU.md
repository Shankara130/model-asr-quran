# Colab GPU Training and Inference

Panduan ini menyiapkan environment untuk menjalankan notebook training `01` dan
inference/corrector `02` dengan GPU. File notebook tidak perlu diubah untuk
mengikuti langkah ini.

## Target Runtime

- Google Colab dengan runtime **GPU**.
- Minimal GPU: T4 16 GB.
- Checkpoint disimpan di Google Drive.
- Cache Hugging Face, audio, dan dataset diproses di disk runtime Colab.

Sebelum menjalankan notebook:

1. Buka `Runtime > Change runtime type`.
2. Pilih `Hardware accelerator: GPU`.
3. Jalankan:

```bash
nvidia-smi
```

Jika command tersebut gagal atau tidak menampilkan GPU, runtime belum GPU.

## Dependency Setup

Repo menyediakan dua file untuk setup Colab:

- `requirements-colab.txt`: dependency Python runtime selain PyTorch.
- `scripts/install_colab_deps.sh`: installer Colab yang menjaga PyTorch CUDA
  tetap GPU-ready.

Jalankan dari root repo di Colab:

```bash
bash scripts/install_colab_deps.sh
python -m pip install -q -e . --no-deps
python scripts/cloud_preflight.py
```

Kenapa `--no-deps` dipakai saat install repo:

- Colab biasanya sudah punya PyTorch CUDA yang cocok dengan image runtime.
- Install editable tanpa `--no-deps` bisa memicu resolver mengganti PyTorch.
- Dependency non-PyTorch sudah dipasang eksplisit oleh script installer.

## Notebook `01`: Training

Urutan aman untuk training:

1. Set `HF_HOME` ke lokasi di `/content`.
2. Verifikasi GPU dengan `nvidia-smi`.
3. Clone atau upload repo ke `/content/model-asr-quran`.
4. Install dependency dengan `scripts/install_colab_deps.sh`.
5. Install project dengan:

```bash
python -m pip install -q -e . --no-deps
```

6. Mount Google Drive.
7. Siapkan audio:
   - gunakan audio yang sudah ada di `/content` jika tersedia,
   - restore dari backup Drive jika ada,
   - download sekali dan backup ke Drive jika belum ada.
8. Build dataset dan vocab.
9. Jalankan training.
10. Jalankan evaluation dan corrector demo.

Checkpoint final ada di:

```text
/content/drive/MyDrive/quran_asr/checkpoints/final
```

Jika runtime Colab disconnect, jalankan ulang setup dependency, mount Drive,
restore audio, lalu lanjutkan training dari checkpoint Drive.

## Notebook `02`: Inference / Corrector

Notebook inference membutuhkan checkpoint hasil training.

Checklist sebelum menjalankan:

- Google Drive sudah mounted.
- Folder checkpoint tersedia:

```text
/content/drive/MyDrive/quran_asr/checkpoints
```

- Dependency sudah dipasang dengan `scripts/install_colab_deps.sh`.
- Project sudah diinstall editable dengan `--no-deps`.

Corrector akan memakai `cuda` jika `torch.cuda.is_available()` bernilai `True`.
Jika tidak, inference tetap bisa jalan di CPU tetapi lebih lambat.

## Preflight

Selalu jalankan preflight sebelum training panjang:

```bash
python scripts/cloud_preflight.py
```

Item yang harus `OK`:

- CUDA GPU
- ffmpeg
- dependency Python
- disk free di `/content`

`HF token` boleh `WARN` jika `logging.hub_repo: null` dan model hanya disimpan
ke Google Drive.

## Local GPU Note

Untuk laptop/PC lokal dengan NVIDIA GPU, pakai virtualenv biasa dan pastikan
PyTorch CUDA terinstall sesuai driver. Jalankan:

```bash
python - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda")
PY
```

Training full tetap disarankan di Colab/Kaggle GPU yang punya VRAM lebih besar.
