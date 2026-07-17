# Model Evaluation Evidence

Tanggal: 17 Juli 2026

## Model dan Metode

- Model: `zipformer_p_quran` (`quran_phoneme_zipformer.int8.onnx`).
- Runtime: `sherpa_onnx`, CPU, greedy search.
- Audio: WAV, mono PCM 16 kHz setelah decoding.
- Reciter sampel: Husary Mujawwad dan Minshawy Murattal.
- Skor: Levenshtein character error rate pada fonem yang dinormalisasi; similarity = `(1 - CER) * 100` dengan batas minimum 0.
- Fingerprint model: SHA-256 disimpan pada setiap hasil API baru, tetapi nilainya tidak dicantumkan dalam dokumen publik ini.

## Bacaan dengan Target Sesuai

| No | Ayat | File | Similarity | CER | Latency | Catatan |
|---:|---|---|---:|---:|---:|---|
| 1 | 1:1 | `001001.wav` | 93.33% | 0.066667 | 0.288 s | Layak demo |
| 2 | 1:2 | `001002.wav` | 94.12% | 0.058824 | 0.287 s | Layak demo |
| 3 | 1:3 | `001003.wav` | 90.00% | 0.100000 | 0.240 s | Layak demo |
| 4 | 1:4 | `001004.wav` | 89.47% | 0.105263 | 0.236 s | Layak demo |
| 5 | 1:5 | `001005.wav` | 75.68% | 0.243243 | 0.355 s | False negative; jangan dipakai sebagai contoh benar utama |
| 6 | 1:6 | `001006.wav` | 92.59% | 0.074074 | 0.309 s | Layak demo |
| 7 | 1:7 | `001007.wav` | 97.33% | 0.026667 | 0.649 s | Layak demo |

Contoh target/prediction 1:1:

```text
Target:     بِسمِ للَااهِ ررَحمَاانِ ررَحِۦۦم
Prediction: بِسمِللَااهِررَحمَاانِررَحِۦۦۦۦم
```

Perbedaan utama berasal dari spasi dan panjang representasi fonem akhir. Evaluator menormalkan spasi tetapi tetap menghitung perbedaan panjang fonem.

## Audio Sengaja Tidak Sesuai Target

Ketiga audio berikut sengaja dinilai terhadap target 1:1 untuk membuktikan pemisahan bacaan berbeda.

| No | Target | Sumber audio | Similarity | CER | Latency |
|---:|---|---|---:|---:|---:|
| 8 | 1:1 | 1:2 | 46.67% | 0.533333 | 0.348 s |
| 9 | 1:1 | 1:5 | 36.67% | 0.633333 | 0.418 s |
| 10 | 1:1 | 1:7 | 43.33% | 0.566667 | 0.821 s |

Hasil menunjukkan pemisahan yang jelas dari sampel target sesuai yang umumnya berada pada 89–97%.

## Validasi Lintas Qari

Tujuh audio Minshawy Murattal diproses melalui provider ASR, decoder audio, dan evaluator
yang sama dengan backend produksi. Model dimuat satu kali dan setiap MP3 didekode menjadi
mono PCM 16 kHz sebelum inference.

| No | Ayat | File | Similarity | CER | Latency |
|---:|---|---|---:|---:|---:|
| 11 | 1:1 | `001001.mp3` | 100.00% | 0.000000 | 0.147 s |
| 12 | 1:2 | `001002.mp3` | 100.00% | 0.000000 | 0.158 s |
| 13 | 1:3 | `001003.mp3` | 100.00% | 0.000000 | 0.120 s |
| 14 | 1:4 | `001004.mp3` | 100.00% | 0.000000 | 0.115 s |
| 15 | 1:5 | `001005.mp3` | 94.59% | 0.054054 | 0.173 s |
| 16 | 1:6 | `001006.mp3` | 96.30% | 0.037037 | 0.153 s |
| 17 | 1:7 | `001007.mp3` | 98.67% | 0.013333 | 0.399 s |

Hasil Minshawy memperlihatkan bahwa model dapat mengenali qari kedua pada sampel ini.
Perbedaan besar ayat 1:5 antara Husary (75.68%) dan Minshawy (94.59%) menunjukkan bahwa
kalibrasi threshold harus menggunakan lebih banyak qari dan kondisi rekaman.

## Interpretasi Threshold Sementara

- Sampel sesuai yang diuji berada pada 75.68-100.00%.
- Sampel sengaja tidak sesuai berada pada 36.67-46.67%.
- Rentang di antara kelompok tersebut belum cukup terkalibrasi untuk keputusan universal.
- Untuk video, gunakan Minshawy 1:1 atau Husary 1:1 sebagai contoh sesuai dan mismatch
  1:2 terhadap target 1:1 sebagai contoh berbeda.

## Self-Retry dan Pengulangan

Regression suite `tests/test_repeat_aware_retry.py` lulus bersama test backend terfokus. Kasus yang dicakup meliputi:

- frasa salah lalu diulang benar dalam satu take;
- preferensi kandidat retry yang lebih baru;
- pelestarian fonem awal saat retry inline;
- pengulangan ayat/frasa tanpa menaikkan skor melalui duplikasi mentah.

## Keterbatasan

- Empat belas sampel benar berasal dari dua qari dan satu surah; ini bukti operasional,
  bukan evaluasi generalisasi populasi.
- Ayat 1:5 menghasilkan 75.68% pada audio referensi yang benar, menunjukkan kemungkinan false negative pada pengulangan fonem akhir.
- Similarity/CER mengukur kemiripan urutan fonem dan belum merupakan penilaian tajwid klinis atau fatwa benar-salah.
- Noise, mikrofon, tempo, gema, dan variasi qari dapat memengaruhi prediction.
- Suara perempuan, anak, perangkat berbeda, dan noise nyata belum tersedia dalam dataset
  evidence ini dan masih memerlukan pengujian anggota tim.
- Mismatch ayat membuktikan diskriminasi bacaan berbeda, tetapi bukan pengganti rekaman kesalahan makhraj yang terkontrol.
- Latency di atas hanya inference model dalam proses yang sudah memuat model; tidak termasuk upload, jaringan, atau cold start.
