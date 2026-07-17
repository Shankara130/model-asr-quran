# P1 Readiness Checklist

Tanggal: 17 Juli 2026

## Siap dan Terbukti

- [x] Backend dapat startup dan restart tanpa macet.
- [x] Health, readiness, Swagger, dan OpenAPI dapat dibuka.
- [x] Supabase PostgreSQL, Auth, RLS, dan grant diverifikasi.
- [x] Multipart dan chunked upload benar-benar menerima audio.
- [x] ONNX `zipformer_p_quran` dipanggil melalui `sherpa_onnx`.
- [x] Result, highlight, metadata model, dan insight tersimpan serta dapat diambil setelah restart.
- [x] Rekaman pengguna dihapus setelah evaluasi; lokasi database dikosongkan.
- [x] Orphan runtime dibersihkan saat startup.
- [x] Error model, audio, auth, database readiness, dan result tidak ditemukan ditangani.
- [x] Queue wait, inference timeout, rate limit, MIME, durasi, checksum, dan ownership dibatasi.
- [x] Dependency audit tidak menemukan vulnerability yang diketahui setelah remediasi.
- [x] Tersedia request/response evidence tanpa secret.
- [x] Tujuh belas evaluasi model: 14 sesuai dari dua qari dan tiga mismatch.
- [x] Self-retry terbaru dan pengulangan dalam satu take memiliki regression test.
- [x] Keterbatasan dan panduan video ditulis.

## Wajib Dikonfirmasi Tim Sebelum Rekaman Final

- [ ] Jalankan satu dry-run video lengkap menggunakan akun `adit` tanpa menampilkan token.
- [ ] Rekam minimal satu suara anggota tim pada perangkat yang dipakai saat demo.
- [ ] Pastikan contoh live terpilih tidak menghasilkan output aneh sebelum take final.
- [ ] Uji kontrak login-upload-evaluate dari source Flutter ketika repository aplikasi tersedia.
- [ ] Periksa Supabase Security Advisor dari dashboard setelah schema terakhir.

## P2 Setelah Submission

- Kalibrasi threshold dengan dataset berlabel yang mencakup lebih banyak qari, suara perempuan,
  anak, tempo, mikrofon, dan noise.
- Tambahkan rate limiter bersama bila backend dijalankan dengan beberapa worker/instance.
- Tambahkan E2E dua akun nyata dan WebSocket dari Flutter.
- Bentuk confusion matrix fonem dari kesalahan makhraj yang direkam dan dilabeli secara
  terkontrol; mismatch ayat saat ini tidak cukup untuk klaim confusion makhraj.

## Keputusan Go/No-Go

Backend dan model layak untuk video demonstrasi terkontrol. Submission belum boleh mengklaim
akurasi populasi, penilaian tajwid final, dukungan seluruh jenis suara/perangkat, atau threshold
universal. Lima konfirmasi operasional dan pemeriksaan dashboard di atas tetap dilakukan oleh
tim pada perangkat rekaman final.
