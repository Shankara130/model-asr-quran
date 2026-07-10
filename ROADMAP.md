## Checklist yang belum terpenuhi

```
python -m web.app
```

### Milestone 1 — Fondasi evaluasi

* [ ] Pastikan semua hasil `word_results` selalu punya `tajwid_feedback`
* [ ] Hindari kartu kosong saat data error
* [ ] Hindari pesan koreksi yang duplikat
* [ ] Ganti label **“Kata yang perlu diperiksa”** menjadi **“Bagian bacaan yang perlu diperiksa”**
* [ ] Bedakan hasil kata tunggal dan gabungan antarkata
* [ ] Tambahkan fallback saat segmentasi gagal
* [ ] Uji minimal 10 ayat benar
* [ ] Uji minimal 10 ayat sengaja salah

### Milestone 2 — Koreksi tajwid dasar

#### Mad

* [ ] Deteksi mad terlalu pendek
* [ ] Deteksi mad terlalu panjang
* [ ] Deteksi mad sesuai
* [ ] Bedakan mad dari vokal biasa
* [ ] Tampilkan lokasi mad pada bagian ayat
* [ ] Hindari false warning akibat alignment bergeser

#### Ghunnah

* [ ] Deteksi ghunnah terlalu pendek
* [ ] Deteksi ghunnah terlalu panjang
* [ ] Deteksi ghunnah sesuai
* [ ] Bedakan `ن`, `م`, dan `ں`
* [ ] Bedakan ghunnah dalam kata dan antarkata
* [ ] Hindari semua pengulangan `ن/م` otomatis dianggap ghunnah

#### Tasydid

* [ ] Deteksi tasydid hilang
* [ ] Deteksi penekanan tasydid terlalu pendek
* [ ] Deteksi penekanan berlebih
* [ ] Bedakan tasydid biasa dan ghunnah musyaddadah
* [ ] Buat pesan khusus seperti “Penekanan huruf بّ kurang terdengar”

#### Harakat

* [ ] Deteksi fathah menjadi kasrah
* [ ] Deteksi fathah menjadi dhammah
* [ ] Deteksi kasrah menjadi fathah
* [ ] Deteksi kasrah menjadi dhammah
* [ ] Deteksi dhammah menjadi fathah
* [ ] Deteksi dhammah menjadi kasrah
* [ ] Deteksi harakat hilang
* [ ] Deteksi harakat tambahan

#### Huruf dan makhraj

* [ ] Kelompokkan huruf yang sering tertukar
* [ ] Buat pesan makhraj yang spesifik
* [ ] Bedakan salah huruf dan salah alignment
* [ ] Tambahkan confidence sebelum memberi teguran makhraj
* [ ] Hindari klaim pasti seperti “makhraj salah” bila model hanya kurang yakin

---

## Milestone 3 — Segmentasi kata dan antarkata

* [ ] Pemetaan fonem ke kata Arab yang benar
* [ ] Satu kartu dapat memuat lebih dari satu kata
* [ ] Label Arab sesuai dengan segmen fonem
* [ ] Segmentasi tetap benar walaupun prediksi tidak memiliki spasi
* [ ] Segmentasi tetap benar saat satu huruf hilang
* [ ] Segmentasi tetap benar saat ada bunyi tambahan
* [ ] Segmentasi tidak menggabungkan terlalu banyak kata
* [ ] Segmentasi tidak memotong hukum tajwid antarkata
* [ ] Simpan indeks awal dan akhir setiap segmen
* [ ] Tandai bagian salah langsung pada teks ayat

Contoh struktur yang belum ada:

```python
{
    "start_word": 1,
    "end_word": 2,
    "arabic_text": "نَارٌ مُّؤْصَدَةٌ",
    "target_phoneme": "نَاارُممممُءصَدَه",
    "detected_phoneme": "نَاارُلمُءصَدَ",
}
```

---

## Milestone 4 — Metadata hukum tajwid target

* [ ] Setiap ayat memiliki anotasi hukum tajwid
* [ ] Setiap anotasi punya posisi karakter atau kata
* [ ] Setiap anotasi punya target fonem
* [ ] Setiap anotasi punya kategori hukum
* [ ] Setiap anotasi punya ekspektasi durasi atau pola

Hukum yang belum diimplementasikan secara eksplisit:

* [ ] Mad thabi’i
* [ ] Ghunnah musyaddadah
* [ ] Idgham bighunnah
* [ ] Idgham bila ghunnah
* [ ] Ikhfa
* [ ] Iqlab
* [ ] Izhar halqi
* [ ] Qalqalah
* [ ] Alif lam syamsiyah
* [ ] Alif lam qamariyah
* [ ] Tafkhim
* [ ] Tarqiq

### Struktur anotasi yang dibutuhkan

```python
{
    "rule": "idgham_bighunnah",
    "start_word": 1,
    "end_word": 2,
    "arabic_text": "نَارٌ مُّؤْصَدَةٌ",
    "expected_pattern": "مممم",
    "minimum_repetition": 3,
    "maximum_repetition": 5,
}
```

---

## Milestone 5 — Logika koreksi berbasis hukum

* [ ] Jangan menyimpulkan tajwid hanya dari operasi edit
* [ ] Bandingkan prediksi terhadap metadata hukum target
* [ ] Pisahkan koreksi fonem dan koreksi tajwid
* [ ] Beri prioritas pada koreksi paling penting
* [ ] Gabungkan peringatan yang saling berkaitan
* [ ] Hindari tiga teguran untuk satu kesalahan yang sama
* [ ] Tambahkan tingkat keyakinan koreksi
* [ ] Tambahkan status `sesuai`, `perlu diperiksa`, dan `tidak dapat dinilai`

Contoh output ideal:

```python
{
    "rule": "ghunnah",
    "status": "too_short",
    "confidence": 0.87,
    "message": "Dengung pada مّ terdeteksi terlalu pendek.",
}
```

---

## Milestone 6 — Evaluasi audio

Ini belum terpenuhi dan merupakan bagian riset lebih lanjut.

* [ ] Simpan audio hasil rekaman
* [ ] Dapatkan timestamp setiap token
* [ ] Forced alignment target dengan audio
* [ ] Ukur durasi mad
* [ ] Ukur durasi ghunnah
* [ ] Ukur durasi tasydid
* [ ] Ukur energi bunyi
* [ ] Ukur jeda antarkata
* [ ] Ukur confidence setiap fonem
* [ ] Deteksi audio terlalu pelan
* [ ] Deteksi noise tinggi
* [ ] Deteksi rekaman terpotong

---

## Milestone 7 — Dataset evaluasi

* [ ] Dataset bacaan benar
* [ ] Dataset bacaan salah
* [ ] Kesalahan mad pendek
* [ ] Kesalahan mad panjang
* [ ] Kesalahan ghunnah pendek
* [ ] Kesalahan ghunnah panjang
* [ ] Kesalahan tasydid
* [ ] Kesalahan harakat
* [ ] Kesalahan makhraj
* [ ] Kesalahan hukum antarkata
* [ ] Rekaman dari beberapa orang
* [ ] Rekaman laki-laki dan perempuan
* [ ] Variasi mikrofon
* [ ] Variasi ruangan
* [ ] Label validasi dari penguji kompeten
* [ ] Pembagian train, validation, dan test

---

## Milestone 8 — Metrik pengujian

* [ ] Akurasi ASR per fonem
* [ ] CER per ayat
* [ ] CER per kata
* [ ] Akurasi lokasi kesalahan
* [ ] Akurasi kategori tajwid
* [ ] Precision deteksi kesalahan
* [ ] Recall deteksi kesalahan
* [ ] F1-score
* [ ] False warning rate
* [ ] False negative rate
* [ ] Agreement dengan penguji manusia
* [ ] Confusion matrix huruf hijaiyah
* [ ] Confusion matrix kategori tajwid

---

## Milestone 9 — Pengalaman pengguna

* [ ] Warna berbeda untuk mad, ghunnah, harakat, dan makhraj
* [ ] Sorot kata yang salah pada ayat Arab
* [ ] Tombol putar ulang rekaman pengguna
* [ ] Tombol dengarkan bacaan contoh per bagian
* [ ] Saran perbaikan singkat
* [ ] Riwayat latihan
* [ ] Skor perkembangan
* [ ] Daftar kesalahan paling sering
* [ ] Latihan ulang bagian yang salah
* [ ] Mode pemula dan lanjutan
* [ ] Penjelasan bahwa hasil adalah bantuan, bukan fatwa penilaian bacaan

---

## Prioritas pengerjaan sekarang

Urutan paling masuk akal:

1. [ ] Perbaiki segmentasi antarkata
2. [ ] Buat metadata hukum tajwid target
3. [ ] Stabilkan mad, ghunnah, tasydid, dan harakat
4. [ ] Hilangkan teguran duplikat
5. [ ] Buat dataset uji sengaja benar dan salah
6. [ ] Hitung precision, recall, dan false warning
7. [ ] Baru masuk hukum tajwid lanjutan dan analisis audio

Untuk kondisi proyekmu saat ini, fokus terdekat adalah **segmentasi antarkata dan metadata hukum tajwid**, bukan menambah UI lagi.
