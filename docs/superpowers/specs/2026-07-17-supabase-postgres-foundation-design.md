# Supabase PostgreSQL Foundation Design

## Scope

Tahap ini menyiapkan fondasi database produksi untuk backend Sobat Ngaji. Cakupannya adalah kompatibilitas model SQLAlchemy dengan PostgreSQL, pengamanan tabel aplikasi di Supabase, penerapan schema, seed idempotent, dan sinkronisasi pengguna Supabase Auth. Endpoint audio, inference, dan evaluasi end-to-end berada pada tahap berikutnya.

## Decisions

- FastAPI mengakses PostgreSQL melalui `postgresql+asyncpg` dan Supabase transaction pooler.
- Supabase Auth tetap menjadi sumber identitas. Tabel `public.users` adalah profil aplikasi dengan UUID yang sama seperti `auth.users.id`, bukan penyimpan password autentikasi.
- Tabel aplikasi tetap berada di schema `public` agar perubahan terhadap ORM tetap kecil.
- Seluruh tabel aplikasi dicabut dari role `anon` dan `authenticated`, RLS diaktifkan tanpa policy akses klien, dan hanya backend database role yang mengaksesnya.
- Flutter memakai Supabase Auth untuk memperoleh token, tetapi seluruh data aplikasi diakses melalui FastAPI.
- Schema diterapkan sebagai satu transaksi. Kegagalan pada statement mana pun harus me-rollback seluruh perubahan.
- Seed dapat dijalankan berulang kali tanpa duplikasi.

## ORM And Schema Compatibility

Kolom PostgreSQL `timestamptz`, `date`, dan `time` harus dipetakan ke tipe SQLAlchemy native:

- `DateTime(timezone=True)` untuk timestamp.
- `Date` untuk tanggal laporan.
- `Time` untuk waktu pengingat.

Default Python menghasilkan objek `datetime`, `date`, atau `time`, bukan string. Schema respons API tetap melakukan serialisasi ISO melalui Pydantic. SQLite pada test suite tetap didukung oleh tipe SQLAlchemy yang sama.

Nama tabel, primary key, foreign key, array, JSON, status, dan constraint pada model harus sesuai dengan `docs/database_schema.sql`. Pengujian memeriksa metadata model dan operasi insert/read untuk nilai temporal.

## Security Model

Tabel berikut adalah backend-only: `users`, `auth_refresh_tokens`, `user_preferences`, `practice_items`, `practice_item_segments`, `practice_sessions`, `practice_session_realtime_tokens`, `audio_uploads`, `audio_chunks`, `evaluation_results`, `ayah_highlights`, `letter_insights`, `letter_mastery`, `weekly_reports`, `practice_session_events`, dan `request_logs`.

Untuk setiap tabel:

1. Aktifkan RLS.
2. Cabut seluruh privilege dari `anon` dan `authenticated`.
3. Jangan buat policy klien pada tahap ini.

Fungsi trigger `set_updated_at()` menggunakan `security invoker`, menetapkan `search_path` eksplisit, dan privilege eksekusinya dicabut dari `PUBLIC`, `anon`, dan `authenticated`. Trigger internal tetap memperbarui `updated_at` pada tabel terkait.

Backend menggunakan role dari connection string Supabase yang berhak mengelola tabel dan tidak bergantung pada Data API. Service-role key tidak digunakan sebagai password PostgreSQL dan tidak pernah dikirim ke Flutter.

## Schema Deployment

Sebelum penerapan:

- Pastikan driver URL adalah `postgresql+asyncpg`.
- Jalankan `SELECT 1`.
- Periksa collision nama tabel dan hentikan jika database memiliki objek tidak dikenal yang berpotensi tertimpa.
- Audit SQL agar tidak memuat `DROP TABLE`, `TRUNCATE`, atau penghapusan data.

Penerapan menjalankan schema dalam satu transaksi. `DROP TRIGGER IF EXISTS` diperbolehkan karena trigger langsung dibuat ulang dalam transaksi yang sama. Setelah commit, verifikasi tabel, foreign key, index, trigger, RLS, dan privilege role.

## Seed Strategy

Startup backend tidak membuat akun Supabase Auth palsu saat Supabase Auth aktif. Data awal terdiri dari:

- practice item Al-Fatihah dan Juz 30 yang memenuhi batas panjang;
- latihan huruf;
- metadata referensi audio.

Seed practice item menggunakan ID stabil dan hanya menambahkan ID yang belum ada. Menjalankan seed dua kali harus menghasilkan tambahan `0` pada run kedua.

Dev user lokal hanya dibuat ketika Supabase Auth tidak aktif. Pada mode Supabase, profil aplikasi dibuat atau diperbarui ketika token pengguna valid pertama kali diterima. UUID profil harus sama dengan UUID Supabase Auth.

## User Synchronization

`sync_supabase_user` mencari profil berdasarkan UUID terlebih dahulu. Lookup email hanya dipakai untuk migrasi profil lama. Jika email lama ditemukan dengan UUID berbeda, sinkronisasi harus memindahkan identitas secara aman atau menolak konflik; implementasi tidak boleh mengubah primary key yang sudah direferensikan tanpa strategi relasi yang valid.

Data otorisasi tidak boleh diambil dari `user_metadata`. Metadata tersebut hanya boleh dipakai untuk nama tampilan dan avatar. Kepemilikan resource selalu berdasarkan UUID terverifikasi dari endpoint Supabase Auth `/auth/v1/user`.

## Error Handling

- Konfigurasi driver salah: startup gagal cepat dengan pesan konfigurasi yang disensor.
- Database timeout/unreachable: startup gagal dalam batas waktu, bukan macet tanpa batas.
- Schema gagal: transaksi rollback dan tidak menjalankan seed.
- Seed gagal: startup melaporkan tahap seed yang gagal tanpa mencetak credential.
- Token Supabase tidak valid: API mengembalikan error autentikasi standar tanpa membuat profil.
- Konflik email/UUID: API mengembalikan conflict yang dapat ditindaklanjuti dan tidak merusak relasi database.

## Verification

Tahap dianggap selesai hanya jika seluruh bukti berikut tersedia:

1. Koneksi pooler menjalankan `SELECT 1`.
2. Seluruh tabel aplikasi terbentuk dan metadata penting sesuai.
3. RLS aktif pada seluruh tabel backend-only.
4. Role `anon` dan `authenticated` tidak memiliki privilege tabel.
5. Seed pertama menghasilkan item latihan dan seed kedua menambah `0` item.
6. Backend restart tanpa menggandakan seed.
7. Token Supabase valid membuat profil dengan UUID Auth yang sama.
8. Token invalid tidak membuat profil.
9. Test SQLite dan PostgreSQL yang relevan lulus.
10. Nilai credential tidak muncul pada log, bukti, atau Git diff.

## Non-Goals

- Memindahkan audio ke Supabase Storage.
- Memberi Flutter akses langsung ke tabel aplikasi.
- Menguji inference ONNX melalui API.
- Menyusun seluruh bukti video submission.
- Mengubah schema Supabase `auth` yang dikelola platform.
