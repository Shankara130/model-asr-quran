# model-asr-quran (Bahasa Indonesia)

Model **ASR bacaan Quran** (wav2vec2) + **koreksi tingkat kata & harakat**.
Ini adalah **fase model** dari app yang lebih besar (Flutter + Python + WebSocket);
backend dan app mobile menyusul di fase berikutnya.

> English version: [README.md](README.md).

## Apa yang dilakukan

1. **ASR** — men-transcribe bacaan Quran dengan **harakat penuh (tashkeel)**.
2. **Koreksi** — karena teks rujukan (ayat) selalu diketahui, mekanisme inti
   adalah **CTC forced alignment**, bukan ASR bebas. Tiap kata rujukan di-align
   ke audio dan diberi skor, menghasilkan vonis:
   `correct` / `low_confidence` (diduga salah baca) / `skipped` (kata terlewat)
   / `extra` (kata tambahan).

## Data

- **Audio**: [everyayah.com](https://everyayah.com) — MP3 per ayat,
  `https://everyayah.com/data/<Qari>/<SSSAAA>.mp3`.
- **Teks**: teks Uthmani berharakat penuh dari
  [quran.com API](https://api.quran.com/api/v4/quran/verses/uthmani). Alignment
  teks↔audio trivial 1:1 per (surah, ayah).

## Mulai cepat

```bash
make setup          # uv sync — buat venv, install deps
make download       # unduh audio + teks berharakat (default configs/tiny.yaml)
make build          # susun HF Dataset (data/processed)
make vocab          # bangun vocab CTC berharakat
make test           # pytest
```

Training dijalankan di **cloud GPU gratis** (Google Colab / Kaggle) lewat
`notebooks/01_colab_train.ipynb`, yang memanggil entrypoint
`quran_asr.training.train` yang sama dengan `scripts/train.py` lokal. Config
`tiny.yaml` lokal hanya untuk uji coba di M1.

## Batas yang jujur

Forced alignment mengukur **seberapa cocok audio dengan urutan token yang
diharapkan** — ia *belum* bisa memisahkan "harakat salah" dari noise, gema
ruangan, atau tempo. Koreksi setara tajweed butuh pemodelan tingkat fonem +
skor GOP (Goodness-of-Pronunciation), itu **fase 2**, di luar scope ini.

Ceiling realistis dengan data + GPU gratis:
`WER_plain ~5–10%`, `WER_diac ~15–30%` (error harakat dominan). Cukup untuk
"apakah katanya tepat?", belum untuk "apakah tajweed-nya benar?".

## Lisensi

Kode: MIT. Audio © para qari EveryAyah; teks dari quran.com (Tanzil/Uthmani).
