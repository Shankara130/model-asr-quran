# Live Inference

Script inference terpisah:

```bash
python scripts/live_infer_asr.py \
  --model TBOGamer22/wav2vec2-quran-phonetics \
  --audio data/raw/audio/Husary_128kbps_Mujawwad/094001.mp3 \
  --surah 94 \
  --ayah 1
```

Reference bisa diambil otomatis dari `data/raw/text/quran_uthmani.json`:

```bash
python scripts/live_infer_asr.py --audio sample.wav --surah 94 --ayah 1
```

Untuk mic sekali rekam:

```bash
python scripts/live_infer_asr.py --record-seconds 5 --surah 94 --ayah 1
```

Untuk live chunk:

```bash
python scripts/live_infer_asr.py --live --chunk-seconds 4 --surah 94 --ayah 1
```

Output menampilkan transcript, latency, confidence proxy, blank rate, WER/CER,
WER/CER tanpa harakat, correction diff, dan top token probability.

Catatan: mode microphone membutuhkan dependency optional `sounddevice`.
