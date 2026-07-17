# P1 Security Audit

Tanggal: 17 Juli 2026

## Hasil

| Pemeriksaan | Hasil |
|---|---|
| RLS tabel aplikasi | 16/16 aktif |
| Grant tabel untuk `anon`/`authenticated` | 0 |
| Fungsi `SECURITY DEFINER` tidak aman | 0 |
| Execute trigger function oleh client role | 0 |
| Session milik pengguna lain | Disembunyikan sebagai 404 |
| Evaluation result milik pengguna lain | Disembunyikan sebagai 404 |
| Reference-audio key | Wajib enam digit ASCII |
| Rate limit auth | 10 request/menit/IP |
| Rate limit upload | 30 request/menit/IP |
| Rate limit evaluate | 10 request/menit/IP |
| Format rate-limit response | HTTP 429 + `rate_limited` + `Retry-After` + request ID |
| `pip-audit` setelah remediasi | Tidak ada vulnerability yang diketahui |

`pip-audit` awal menemukan `setuptools 81.0.0` dengan `PYSEC-2026-3447`.
Virtualenv diperbarui ke `setuptools 83.0.0`, kemudian audit ulang lulus. Paket lokal
`quran-asr` dilewati karena bukan distribusi PyPI; source-nya diuji dan dilint langsung.

## Supabase Advisor

Supabase CLI/MCP advisor tidak tersedia pada environment ini. Sebagai fallback yang dapat
direproduksi, `scripts/setup_database.py --verify` memeriksa metadata PostgreSQL langsung:

```text
verify=ok tables=16 rls=16 client_grants=0 unsafe_functions=0
```

Pemeriksaan dashboard Supabase Security Advisor tetap disarankan sebelum deployment publik,
terutama setelah perubahan schema berikutnya.

## Batas Audit

- Rate limiter bersifat in-memory per proses; deployment multi-worker memerlukan limiter bersama
  seperti Redis atau gateway rate limiting.
- Pengujian IDOR unit mencakup session dan evaluation result. E2E lintas dua akun belum dijalankan.
- Service-role, database URL, password, dan access token tidak dicantumkan pada evidence.
