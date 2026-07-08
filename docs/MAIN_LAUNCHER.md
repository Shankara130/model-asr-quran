# Main Launcher

Jalankan menu utama dari root repo:

```bash
uv run python main.py
```

Menu ini menyediakan:

- Live ASR dari mic.
- Rekam mic sekali lalu infer.
- Infer dari file audio.
- Train local manual fresh.
- Resume train local manual.

Untuk inference, launcher akan meminta:

- model: HF default, local best, local latest, atau custom;
- surat: pilih dari daftar 114 surat, bisa ketik nomor atau `/nama`;
- ayat: range ayat otomatis dari `data/raw/text/quran_uthmani.json`;
- input audio atau durasi/chunk sesuai mode.

Reference WER/CER otomatis memakai dataset Uthmani lokal.
