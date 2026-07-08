# Catatan Training Lokal RTX 3050

Dokumen ini mencatat kendala dan keputusan selama eksperimen training model ASR
Quran recitation di GPU lokal RTX 3050 6GB. Target fase ini adalah model
transkripsi bacaan Quran, bukan model tajweed penuh.

## Target Metrik

Metrik utama yang dipantau:

- `WER_plain`: word error rate setelah harakat dibuang.
- `CER_plain`: character error rate setelah harakat dibuang.
- `WER` / `CER`: metrik dengan harakat penuh.
- `empty_pred_rate`: rasio prediksi kosong atau hanya harakat.

Loss saja tidak cukup untuk menilai CTC. Model bisa punya loss turun, tetapi
greedy decode tetap kosong. Karena itu contoh decode dan WER/CER harus selalu
dilihat.

## Kendala VRAM

Training dilakukan di RTX 3050 6GB. XLS-R 300M memiliki sekitar 315 juta
parameter, sehingga full fine-tuning tidak realistis untuk eksperimen lokal.
Recipe lokal memakai batch size 1, gradient accumulation, gradient checkpointing,
dan partial unfreeze.

## Kendala Split

Split awal terlalu kecil:

```text
train:      1914
validation: 14
test:       47
```

Validation 14 ayat terlalu noisy untuk membaca WER/CER. Split diperbarui tetap
`by_surah`, tetapi validation/test dibuat lebih besar:

```text
train:      1611
validation: 165
test:       199
```

Split `by_surah` tetap dipakai karena Quran adalah fixed corpus. Random per ayat
bisa membuat evaluasi terlalu mudah.

## Diagnosis Tokenizer

Tokenizer dicek dari sample validation:

```text
TEXT == NORMALIZED == DECODED LABEL
UNK count: 0
pad_token: [PAD] 49
unk_token: [UNK] 48
vocab size: 52
```

Kesimpulan: vocab dan tokenizer aman. Masalah bukan karena karakter Quran atau
harakat tidak masuk vocab.

## Blank Collapse

Recipe awal membuka 2 encoder layer terakhir dengan trainable ratio sekitar 8%.
Hasilnya CTC loss turun, tetapi greedy decode kosong:

```text
PRED: ''
blank frame rate: 0.99999994
top avg token: [PAD] ~0.988
empty_pred_rate: 100%
```

Ini blank collapse. Model memilih blank di hampir semua frame.

## Recipe Anti Blank

Untuk keluar dari blank collapse, training dibuat dua tahap otomatis:

```yaml
model:
  apply_spec_augment: false

training:
  auto_stage: true
  bootstrap_min_epochs: 3
  bootstrap_max_epochs: 4
  bootstrap_empty_threshold: 0.2

  bootstrap_encoder_trainable_layers: 0
  bootstrap_head_learning_rate: 7.0e-4
  bootstrap_blank_logit_bias_init: -2.0
  bootstrap_apply_spec_augment: false

  finetune_encoder_trainable_layers: 1
  finetune_encoder_learning_rate: 5.0e-7
  finetune_head_learning_rate: 3.0e-4
  finetune_apply_spec_augment: false
```

Alurnya:

1. Bootstrap head-only supaya `lm_head` belajar mapping token dasar.
2. Bootstrap berjalan minimal 3 epoch dan maksimal 4 epoch.
3. Trainer pindah ke finetune jika `empty_pred_rate <= 20%` setelah minimum epoch.
4. Finetune membuka 1 encoder layer terakhir dengan LR sangat kecil.
5. SpecAugment tetap mati dulu karena data masih kecil dan head belum stabil.

## Interpretasi Log Terbaru

Run auto-stage terbaru sudah keluar dari blank collapse:

```text
empty_pred_rate: 0.0%
```

Namun WER/CER masih buruk:

```text
WER_plain: ~0.99-1.00
CER_plain: ~0.90-0.96
```

Artinya failure mode sudah berubah. Model tidak lagi diam/blank, tetapi belum
punya alignment akustik-ke-teks yang cukup stabil. Karena data saat ini hanya
sedikit qari, finetune encoder dibuat lebih konservatif agar representasi
pretrained tidak cepat bergeser.

## Catatan Data Qari

Untuk target transkripsi bacaan ngaji lintas pembaca, 1-2 qari cukup untuk
debugging pipeline, tetapi belum cukup untuk generalisasi.

Rekomendasi bertahap:

- 2 qari: baseline lokal dan debugging training loop.
- 5 qari: milestone minimum untuk generalisasi awal.
- 10 qari: lebih sehat untuk model yang ingin dipakai di luar qari training.

Saat dataset sudah 5+ qari, tambahkan evaluasi `held-out reciter`: sebagian qari
tidak masuk train dan hanya dipakai validation/test. Ini mengukur kemampuan
model menghadapi suara pembaca yang belum pernah dilihat.

## Prinsip Evaluasi

Pantau metrik dengan urutan:

1. `empty_pred_rate`: harus rendah.
2. `CER_plain`: progress awal biasanya terlihat di sini.
3. `WER_plain`: target utama tanpa harakat.
4. `CER` / `WER`: target lebih keras karena harakat penuh.
5. Contoh decode manual: wajib, karena loss bisa menipu.

Jangan membaca `final/` saat training dihentikan di tengah. Gunakan `latest/`.
`final/` baru valid setelah training selesai normal.
