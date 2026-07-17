# Supabase Database Evidence

Tanggal verifikasi: 17 Juli 2026 (Asia/Jakarta)

## Konfigurasi

- Database: Supabase PostgreSQL melalui transaction pooler.
- Driver backend: `postgresql+asyncpg`.
- Auth: Supabase Auth.
- Akses data aplikasi: FastAPI backend-only.
- Kredensial, host, UUID, token, email, dan password tidak dicantumkan dalam dokumen ini.

## Schema dan Keamanan

| Pemeriksaan | Hasil |
|---|---:|
| Query koneksi `SELECT 1` | Lulus |
| Tabel aplikasi yang diharapkan | 16 |
| Tabel aplikasi tersedia | 16 |
| Tabel dengan RLS aktif | 16 |
| Direct grant untuk `anon`/`authenticated` | 0 |
| Operasi `DROP TABLE`, `TRUNCATE`, atau `DELETE FROM` dalam schema | 0 |
| Penerapan schema | Satu transaksi, committed |

Tabel aplikasi tidak memiliki policy akses client. Flutter menggunakan Supabase Auth untuk memperoleh token, kemudian mengakses data latihan melalui FastAPI.

## Seed

| Pemeriksaan | Hasil |
|---|---:|
| Practice item sebelum seed | 0 |
| Practice item setelah seed pertama | 615 |
| Practice item setelah seed kedua | 615 |
| Tambahan row pada seed kedua | 0 |
| Dev profile otomatis pada mode Supabase | 0 |

Seed terdiri dari ayat terkurasi Al-Fatihah/Juz 30 dan latihan huruf. ID item stabil membuat operasi dapat dijalankan ulang tanpa duplikasi.

## Startup dan Restart

Lifecycle FastAPI dijalankan dua kali terhadap database yang sama.

| Boot | OpenAPI paths | Practice item | Hasil |
|---:|---:|---:|---|
| 1 | 25 | 615 | Lulus |
| 2 | 25 | 615 | Lulus |

Jumlah seed tidak berubah setelah restart.

## Supabase Auth

Satu akun demo dibuat melalui Supabase Admin Auth dengan nama dan username `adit`. Password acak disimpan hanya dalam `.env` lokal yang diabaikan Git.

| Pemeriksaan | Hasil |
|---|---|
| Login password melalui Supabase Auth | Lulus |
| Validasi access token melalui `/auth/v1/user` | Lulus |
| UUID profile aplikasi sama dengan UUID Auth | Lulus |
| Profile aplikasi tersimpan | 1 row |
| Token invalid ditolak | `auth_invalid_credentials` |
| Token invalid membuat profile | Tidak |

Metadata pengguna hanya digunakan untuk nama tampilan/avatar. Kepemilikan resource menggunakan UUID dari identitas Auth yang terverifikasi.

## Pengujian Lokal

Sebanyak 22 unit/security test terfokus lulus untuk:

- tipe temporal SQLAlchemy;
- keamanan schema;
- guard deployment;
- seed idempotent;
- sinkronisasi profile Supabase;
- result mapping.

Full FastAPI test suite berbasis SQLite belum dapat digunakan sebagai bukti pada environment ini karena `aiosqlite.connect()` macet pada versi 0.21.0 maupun 0.22.1, sedangkan `sqlite3` sinkron berfungsi. Verifikasi database produksi pada tahap ini dilakukan langsung terhadap Supabase PostgreSQL. Masalah harness SQLite ini tidak memengaruhi lifecycle FastAPI yang menggunakan PostgreSQL, tetapi tetap harus dibereskan sebelum klaim seluruh regression suite lulus.
