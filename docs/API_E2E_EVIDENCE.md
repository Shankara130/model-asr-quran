# API End-to-End Evidence

Tanggal: 17 Juli 2026

Semua nilai token, password, URL Supabase, UUID, dan connection string disensor.

## Runtime dan Swagger

| Pemeriksaan | Hasil |
|---|---|
| Uvicorn startup | Lulus |
| `/v1/health` | HTTP 200 |
| `/v1/readiness` | HTTP 200, seluruh komponen ready |
| `/docs` | HTTP 200 |
| `/openapi.json` | HTTP 200 |
| OpenAPI paths | 26 setelah readiness ditambahkan |
| Request ID | Tersedia pada response |

Readiness yang teruji:

```json
{
  "status": "ready",
  "checks": {
    "database": {"ready": true},
    "storage": {"ready": true},
    "ffmpeg": {"ready": true},
    "model": {"ready": true}
  }
}
```

## Auth dan Session

| Request | Hasil |
|---|---|
| Login akun demo `adit` | HTTP 200 |
| Validasi Supabase access token | Lulus |
| `GET /v1/practice-items` | HTTP 200 |
| `POST /v1/practice-sessions` | HTTP 201 |

Backend memvalidasi bearer token melalui Supabase Auth dan menyinkronkan UUID Auth ke profile aplikasi.

## Multipart Upload dan Inference

Sampel: Husary 1:1, WAV, 333760 byte.

| Langkah | Hasil |
|---|---|
| Buat session | HTTP 201 |
| Multipart upload | HTTP 200 |
| File privat tersedia selama inference | Ya, 333760 byte |
| Row `audio_uploads` tersimpan | Ya |
| Request evaluate | HTTP 201 |
| Status pending dapat diambil | Ya |
| Status final | `completed` |
| Match score | 93 |
| Highlight | 4 |
| Result dapat diambil setelah restart | Ya |
| Model name tersimpan | `zipformer_p_quran` |
| Model fingerprint tersimpan | SHA-256, ya |
| File rekaman setelah evaluation final | Dihapus |
| `audio_url`/`storage_key` setelah evaluation | Dikosongkan |

Rekaman pengguna bersifat sekali pakai. Result, skor, highlight, dan metadata model tetap
tersimpan, tetapi retry sesudah evaluation final memerlukan rekaman baru.

## Chunked Upload

File yang sama dibagi menjadi dua chunk dengan SHA-256 per chunk dan checksum final.

| Langkah | Hasil |
|---|---|
| Init | HTTP 200 |
| Chunk 0 | HTTP 200 |
| Chunk 1 | HTTP 200 |
| Complete | HTTP 200 |
| Ukuran assembly | 333760 byte |
| Sama dengan sumber | Ya |

## Error Handling

| Skenario | HTTP | Error code |
|---|---:|---|
| Bearer token invalid | 401 | `auth_invalid_credentials` |
| Audio kosong | 400 | `audio_upload_failed` |
| MIME tidak didukung | 400 | `audio_upload_failed` |
| Evaluation result tidak ditemukan | 404 | `session_not_found` |

Semua response error di atas menyertakan `X-Request-Id` dan payload error standar.

## Endpoint Nyata dan Mock

Nyata dan terhubung ke Supabase/penyimpanan/model:

- Auth signup/login/refresh/logout melalui Supabase Auth.
- Profile dan preferences pada PostgreSQL.
- Practice items dan sessions pada PostgreSQL.
- Multipart dan chunked upload pada filesystem privat + metadata PostgreSQL.
- Evaluation melalui ffmpeg, `sherpa_onnx`, dan ONNX final.
- Evaluation result, highlights, letter insight, dan self-correction pada PostgreSQL.
- Health, readiness, Swagger, dan OpenAPI.

Belum lengkap atau belum dibuktikan untuk video:

- Penyimpanan audio masih filesystem host, belum Supabase Storage.
- WebSocket tersedia tetapi belum diuji dari Flutter pada workspace ini.
- Retention cleanup audio belum dijalankan sebagai scheduled job.
- Full SQLite-based API test harness macet pada environment ini; E2E PostgreSQL nyata digunakan sebagai bukti runtime.
- Source Flutter tidak tersedia di repository ini, sehingga integrasi mobile belum dapat diimplementasikan di sini.
