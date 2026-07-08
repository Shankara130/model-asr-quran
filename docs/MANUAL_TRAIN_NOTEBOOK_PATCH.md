# Manual Training Notebook Patch

Notebook `02_prepare_train_loop.ipynb` berperan sebagai runner dan inspector.
Training loop utama ada di:

- `quran_asr.training.manual_train`
- `scripts/train_manual.py`

## Training Cell

Untuk eksperimen baru, jalankan manual trainer dengan `--no-resume`:

```python
run_cmd([
    sys.executable,
    str(PROJECT_ROOT / "scripts" / "train_manual.py"),
    "--config",
    str(CONFIG_PATH),
    "--no-resume",
])
```

`--no-resume` penting ketika recipe atau split berubah, supaya checkpoint lama
yang mungkin sudah collapse tidak ikut dipakai.

## Recipe Aktif

Config lokal sekarang memakai auto-stage:

```yaml
training:
  auto_stage: true
  bootstrap_min_epochs: 3
  bootstrap_max_epochs: 4
  bootstrap_empty_threshold: 0.2

  bootstrap_encoder_trainable_layers: 0
  bootstrap_head_learning_rate: 7.0e-4
  bootstrap_blank_logit_bias_init: -2.0

  finetune_encoder_trainable_layers: 1
  finetune_encoder_learning_rate: 5.0e-7
  finetune_head_learning_rate: 3.0e-4
```

Trainer pindah dari bootstrap ke finetune setelah minimal 3 epoch dan
`empty_pred_rate <= 20%`, atau ketika bootstrap mencapai 4 epoch.

## Monitoring Checkpoint

Jika training dihentikan sebelum selesai, baca:

```python
checkpoint_dir = OUTPUT_DIR / "latest"
```

Untuk checkpoint terbaik sejauh ini:

```python
checkpoint_dir = OUTPUT_DIR / "best"
```

Jangan pakai `final/` untuk monitoring tengah run. `final/` baru dibuat setelah
training selesai normal.

## Plot History

History untuk monitoring tengah run ada di:

```python
history_path = OUTPUT_DIR / "latest" / "training_history.json"
```

History sekarang menyimpan kolom `stage`, sehingga grafik bisa dibaca sebagai
bootstrap atau finetune tanpa menebak dari log terminal.
