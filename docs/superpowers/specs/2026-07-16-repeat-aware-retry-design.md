# Repeat-Aware Retry Design

## Goal

Sobat Ngaji harus bisa menangani dua bentuk pengulangan bacaan:

- User merekam ulang setelah hasil sebelumnya salah. Hasil utama yang dipakai app adalah attempt terbaru.
- User mengulang bagian yang salah di dalam satu rekaman. Evaluasi tidak boleh menghukum attempt lama dua kali jika ada koreksi diri yang lebih baru dan cukup cocok.

## Current Baseline

Backend saat ini membuat satu `evaluation_results` baru setiap request evaluasi. `PracticeSession` langsung menjadi `completed` saat evaluasi selesai, tetapi endpoint retry sudah dapat membuat result baru untuk sesi yang sama. Riwayat result sudah tersimpan, sehingga attempt antar rekaman bisa dihitung dari urutan `evaluation_results.created_at` tanpa tabel baru untuk tahap pertama.

Pipeline evaluasi saat ini:

1. Resolve audio terbaru atau `audio_id` tertentu.
2. Jalankan ASR.
3. Jalankan `evaluate_prediction(target_phoneme, prediction)`.
4. Map hasil ke score, highlights, dan letter insights.
5. Simpan result dan highlights.

## Proposed Architecture

### Attempt History Without Migration

Tahap pertama tidak menambah kolom database. Attempt metadata dihitung saat response:

- `attemptNumber`: posisi result dalam semua result sesi, diurutkan `created_at`.
- `isLatest`: `true` hanya untuk result terbaru dalam sesi.

Saat user retry dengan audio baru, backend tetap membuat `EvaluationResult` baru. UI harus memakai result terbaru sebagai status utama. Result lama tetap tersedia sebagai riwayat, tetapi tidak boleh menentukan status aktif.

### Repeat-Aware Evaluation

Tambahkan layer pure Python sebelum alignment final:

- Normalisasi target dan prediction.
- Jika prediction lebih panjang dari target, cari kandidat substring yang paling cocok dengan target.
- Jika ada beberapa kandidat dengan skor sama atau sangat dekat, pilih kandidat paling akhir karena itu paling mungkin self-correction terbaru.
- Jalankan alignment final terhadap kandidat terpilih.
- Laporkan metadata `self_corrections` untuk memberi tahu app bahwa bagian awal prediction diabaikan karena digantikan bacaan yang lebih baru.

Aturan konservatif:

- Jika prediction tidak lebih panjang dari target secara bermakna, pakai prediction asli.
- Jika kandidat terbaik tetap sangat buruk, jangan klaim koreksi diri sebagai benar; cukup pakai kandidat terbaik dan confidence akan tetap rendah.
- Hasil final tetap "evaluasi awal", bukan keputusan tajwid final.

### API Shape

Tambahan field bersifat backwards-compatible:

- `result.attemptNumber`
- `result.isLatest`
- `result.selfCorrections[]`

`selfCorrections[]` minimal berisi:

- `type`: `prefix_superseded`
- `detected`: phoneme yang diabaikan
- `selected`: kandidat phoneme yang dipakai untuk evaluasi
- `note`: pesan lokal pendek

## Testing

Test minimal:

- Prediction biasa tetap dievaluasi seperti sebelumnya.
- Prediction berisi bacaan salah lalu bacaan benar memilih kandidat terakhir yang benar.
- Prediction berisi dua kandidat sama-sama cocok memilih kandidat terakhir.
- Response result menandai result terbaru sebagai `isLatest=true` dan result lama sebagai `false`.

## Out of Scope

Tahap ini belum membuat forced alignment timestamp audio, belum menambah metadata tajwid berbasis durasi, dan belum menambah tabel attempt khusus. Tabel khusus bisa dibuat setelah kontrak app stabil dan kebutuhan analitik attempt lebih jelas.
