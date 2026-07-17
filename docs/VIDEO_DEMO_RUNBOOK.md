# Video Demo Runbook

## Persiapan

1. Pastikan `.env` terisi dan tidak tampil pada layar rekaman.
2. Jalankan verifikasi database:

```bash
rtk proxy .venv/bin/python scripts/setup_database.py --verify
```

3. Jalankan backend:

```bash
rtk proxy .venv/bin/python -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8010
```

4. Buka `http://127.0.0.1:8010/docs`.
5. Siapkan `001001.wav` sebagai contoh benar dan salah satu audio mismatch sebagai perbandingan.

## Urutan Rekaman

1. Tampilkan arsitektur: client → FastAPI → ffmpeg/sherpa ONNX → Supabase PostgreSQL/Auth.
2. Tampilkan terminal startup hingga `Application startup complete`.
3. Buka `/v1/readiness` dan tunjukkan empat komponen ready.
4. Buka Swagger dan tunjukkan kelompok auth, practice, audio, evaluation, dan insights.
5. Login sebagai `adit`; sensor token pada response atau gunakan script demo yang tidak mencetak token.
6. Ambil practice item Al-Fatihah 1 dan buat session.
7. Upload `001001.wav`.
8. Request evaluation dan jelaskan status `queued/processing`.
9. Ambil result final: status completed, skor 93, empat highlight.
10. Tunjukkan row evaluation di Supabase tanpa membuka credential.
11. Restart backend dan ambil result yang sama untuk membuktikan persistence.
12. Tampilkan perbandingan sampel benar 93.33% dan mismatch 36–47%.
13. Tampilkan self-retry/pengulangan dari UI tester atau regression evidence.
14. Tutup dengan keterbatasan model, terutama false negative ayat 1:5.

## Narasi Transparansi

Model menghasilkan transkripsi fonem awal. Sistem kemudian membandingkannya dengan fonem target ayat menggunakan alignment dan CER. Hasil adalah evaluasi awal untuk membantu latihan, bukan keputusan tajwid final. Skor dapat dipengaruhi qari, mikrofon, noise, tempo, dan representasi panjang fonem.

## Rencana Cadangan

- Jika Supabase tidak dapat dijangkau, tampilkan evidence yang sudah direkam; jangan mengklaim request live berhasil.
- Jika inference cold start lambat, mulai backend sebelum merekam dan gunakan health/readiness untuk membuktikan kesiapan.
- Jangan gunakan Al-Fatihah 1:5 sebagai contoh bacaan benar utama karena hasil referensinya masih 75.68%.
- Jangan tampilkan `.env`, access token, service-role key, database URL, atau UUID pengguna.

## Integrasi Flutter

Source Flutter tidak ada di workspace model ini. Agent Flutter perlu menerima:

- base URL backend;
- Supabase URL dan anon/publishable key saja;
- kontrak OpenAPI dari `/openapi.json`;
- flow login → practice items → session → upload → evaluate → GET result;
- larangan memasukkan service-role key atau PostgreSQL URL ke aplikasi.
