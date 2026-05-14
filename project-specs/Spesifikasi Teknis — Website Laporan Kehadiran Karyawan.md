# Spesifikasi Teknis — Website Laporan Kehadiran Karyawan

## Ringkasan Proyek

Website untuk memproses data absensi (scanlog) dari mesin fingerprint menjadi laporan kehadiran karyawan dalam format `.xlsx`. Pengguna mengunggah file spreadsheet mentah, dan sistem menghasilkan file Excel baru dengan **4 sheet**:

1. **Data Mentah** — data asli dari scanlog (referensi)
2. **Rekapitulasi** — ringkasan keterlambatan bulanan per karyawan
3. **Laporan Individual** — template lookup satu karyawan (ganti nama via dropdown)
4. **Data Harian** — flat table sumber data untuk semua formula lookup (visible, dapat diedit)

---

## Arsitektur Sistem

```
flowchart LR
    A["Pengguna"] -->|Upload .xlsx| B["Website (Flask)"]
    B -->|Proses Data| C["processor.py"]
    C -->|Generate| D["excel_writer.py"]
    D -->|Output .xlsx| A
```

### Tech Stack

- **Backend**: Python 3.9+ dengan Flask
- **Library Utama**: `openpyxl` (baca/tulis Excel), `pandas` (pengolahan data), `xlrd` (baca file `.xls` lama)
- **Frontend**: HTML dengan form upload drag-and-drop
- **Hosting**: Render / Railway / VPS

---

## Struktur Proyek

```
attendance-report/
├── app.py                 # Aplikasi utama Flask
├── processor.py           # Engine pemrosesan data
├── excel_writer.py        # Generator file Excel output
├── templates/
│   └── index.html         # Halaman upload
├── requirements.txt
└── uploads/               # Folder sementara (auto-dibuat)
└── output/                # Folder output (auto-dibuat)
```

---

## Format Input

File `.xlsx` atau `.xls` dari mesin fingerprint. Header data ada di **baris ke-2** (baris 1 diabaikan). Kolom wajib:

| Kolom | Tipe | Keterangan |
|---|---|---|
| PIN | Integer | ID unik karyawan di mesin fingerprint |
| NIP | Text | Nomor Induk Pegawai |
| Nama | Text | Nama karyawan |
| Jabatan | Text | Jabatan karyawan |
| Departemen | Text | Departemen |
| Kantor | Text | Lokasi kantor |
| Tanggal | Date | Tanggal absensi (DD-MM-YYYY atau format umum lainnya) |
| Scan 1 | Time | Scan pertama (jam masuk) — HH:MM:SS |
| Scan 2 | Time | Scan kedua (jam keluar) — opsional |
| Scan 3 | Time | Scan ketiga jika ada — opsional |

---

## Format Output

Nama file output: `Laporan_Kehadiran_[BulanTahun].xlsx`  
Bulan dan tahun dideteksi otomatis dari data yang diunggah, berdasarkan **bulan yang paling sering muncul** di seluruh baris data (bukan tanggal paling awal). Ini mencegah baris carry-over dari bulan tetangga menggeser bulan referensi.

---

### Sheet 1 — Data Mentah

Salinan data asli dari file yang diunggah tanpa perubahan. Berfungsi sebagai referensi.

---

### Sheet 2 — Rekapitulasi

**Judul:** REKAPITULASI LAPORAN KEHADIRAN KARYAWAN TECTONA GROUP — BULAN [Bulan Tahun]

Satu baris per karyawan. Header dua baris (baris 5–6):

| Kolom | Header | Sumber | Keterangan |
|---|---|---|---|
| A | No | Otomatis | Nomor urut |
| B | Nama Karyawan | Data mentah | Nama karyawan |
| C | Cuti | 🔲 Kosong | Diisi manual |
| D | Sakit | 🔲 Kosong | Diisi manual |
| E | Izin | 🔲 Kosong | Diisi manual |
| F | Dinas Lapangan | 🔲 Kosong | Diisi manual |
| G | Terlambat Masuk — Jam | Formula Excel | `=INT(I/60)` — total jam terlambat |
| H | Terlambat Masuk — Menit | Formula Excel | `=MOD(I,60)` — sisa menit |
| I | Jumlah Dalam Menit | Formula Excel | `=SUMIF(Data Harian!A, nama, Data Harian!H)` |
| J | Denda/Menit Rp. | 🚩 Kosong | Tarif per menit — diisi manual |
| K | Total | Formula Excel | `=IF(AND(I<>"",J<>""), I*J, "-")` |
| L | Sangsi 20X | Default 20 | Bisa diedit per karyawan |
| M | Jumlah | Formula Excel | `=IF(AND(K<>"-",K<>""), K*L, "-")` |

Kolom G, H, dan I dihitung dari **Data Harian** (bukan hardcode). Kolom J dan manual entries (C–F) diisi oleh pengguna setelah download.

---

### Sheet 3 — Laporan Individual

Template satu halaman untuk satu karyawan. Pengguna memilih nama dari **dropdown di C6**, dan seluruh data harian otomatis terisi via formula INDEX-MATCH dari sheet Data Harian.

**Layout:**

| Baris | Konten |
|---|---|
| 1 | ⚠ Peringatan: sheet ini read-only, edit Catatan (Manual) di sheet Data Harian |
| 2 | Judul "LAPORAN KEHADIRAN KARYAWAN" |
| 5 | Fingerprint ID (auto-lookup dari C6) |
| 6 | **Nama Karyawan** — dropdown (sel C6, satu-satunya sel yang dapat diedit) |
| 7–8 | Header kolom (double-row merged) |
| 9–(8+hari) | Data harian (semua dari formula lookup) |

**Kolom data harian:**

| Kolom | Header | Sumber di Data Harian |
|---|---|---|
| A | Hari | Kolom C |
| B | Tanggal | Kolom D |
| C | Jam Kerja | Kolom E |
| D | Jam Masuk | Kolom F |
| E | Jam Keluar | Kolom G |
| F | Jam Terlambat | Kolom I (string display) |
| G | Catatan (Otomatis) | Kolom J |
| H | Catatan (Manual) | Kolom N |

**Sheet protection:** Seluruh sheet terkunci kecuali C6 (dropdown nama). Excel menampilkan peringatan jika pengguna mencoba mengedit sel lain.

**Weekend highlighting:** Baris Sabtu dan Minggu otomatis diberi highlight biru muda + font merah via conditional formatting.

---

### Sheet 4 — Data Harian

Flat table berisi data harian semua karyawan. **Visible dan dapat diedit** (tidak disembunyikan). Berfungsi sebagai sumber data untuk semua formula lookup di Rekapitulasi dan Laporan Individual.

**Auto-filter** aktif pada baris header (baris 1). **Lebar kolom** disesuaikan otomatis berdasarkan konten terpanjang di setiap kolom (maks 40 karakter).

**Kolom (A–N):**

| Kolom | Header | Keterangan |
|---|---|---|
| A | Nama | Nama karyawan |
| B | No Hari | Nomor hari dalam bulan (1–31) |
| C | Hari | Nama hari singkat (Sen, Sel, …) |
| D | Tanggal | Tanggal format DD-MM-YYYY |
| E | Jam Kerja | Default: 08:00-17:00 |
| F | Jam Masuk | Waktu scan masuk (HH:MM:SS) |
| G | Jam Keluar | Waktu scan keluar — scan terakhir yang tersedia |
| H | Menit Terlambat | **Angka** — menit terlambat (digunakan SUMIF di Rekapitulasi) |
| I | Jam Terlambat | **String** — format display, misal "5 menit" atau "1 jam 5 menit" |
| J | Catatan Otomatis | Diisi sistem otomatis |
| K | Is Weekend | 1 = hari libur, 0 = hari kerja |
| L | PIN | ID fingerprint karyawan |
| M | Key | Kunci lookup: "NamaKaryawan\|NoHari" |
| N | Catatan (Manual) | **Diisi pengguna** — ditarik ke Laporan Individual via lookup |

---

## Aturan Bisnis

### Jam Kerja

- Standar: **08:00–17:00** untuk semua karyawan

### Keterlambatan

- Karyawan dianggap **terlambat** jika jam masuk > 08:00 (membandingkan jam dan menit saja, detik diabaikan)
- `08:00:59` → **0 menit terlambat**
- `08:01:30` → **1 menit terlambat**
- `08:05:59` → **5 menit terlambat**
- Formula: `menit_terlambat = (jam × 60 + menit) − 480`

### Aturan Hari Pertama

- **Hari pertama setiap bulan (tanggal 1) tidak dihitung keterlambatan**, karena sering hanya berisi scan keluar sisa shift malam bulan sebelumnya.

### Penalti

- **Denda** = Total menit terlambat × Tarif per menit (diisi manual di kolom J Rekapitulasi)
- **Sangsi** = Denda × Pengali sangsi (default 20, dapat diedit)
- Kolom Total dan Jumlah menggunakan **formula Excel** agar otomatis terhitung saat pengguna mengisi tarif

### Interpretasi Scan

| Jumlah Scan | Interpretasi | Catatan Otomatis |
|---|---|---|
| 0 scan | Tidak hadir / data hilang | `Tidak ada scan` |
| 1 scan | Lupa scan keluar | `Hanya scan masuk` |
| 2 scan | Normal | *(kosong)* |
| 3 scan | Anomali | `3 scan terdeteksi` |
| Sabtu | Weekend | `Sabtu` |
| Minggu | Weekend | `Minggu` |

---

## Validasi Input

Sebelum diproses, sistem memvalidasi:

- File berformat `.xlsx` atau `.xls`
- Kolom wajib ada: PIN, NIP, Nama, Tanggal, Scan 1
- Format tanggal valid
- Tidak ada baris duplikat (PIN + Tanggal yang sama lebih dari sekali)

Jika validasi gagal, pesan error ditampilkan di halaman upload.

---

## Alur Pengguna

1. Buka website
2. Pilih file `.xlsx` atau `.xls` dari mesin fingerprint (drag-and-drop atau klik)
3. Klik **"Proses & Download Laporan"**
4. Tunggu proses (biasanya < 5 detik)
5. Download file `.xlsx` hasil
6. Buka di Excel:
   - **Rekapitulasi**: isi kolom Cuti/Sakit/Izin/Dinas Lapangan dan Denda/Menit per karyawan
   - **Data Harian**: isi kolom N (Catatan Manual) untuk catatan harian per baris
   - **Laporan Individual**: pilih nama dari dropdown untuk melihat laporan per karyawan

---

## Catatan Teknis

- Semua formula penalti di Rekapitulasi adalah **formula Excel** (bukan nilai statis) agar pengguna dapat mengubah tarif dan hasilnya terhitung otomatis
- Formula lookup di Laporan Individual menggunakan **INDEX + MATCH** pada kolom kunci (format `Nama|NoHari`) — tidak memerlukan array formula, kompatibel dengan semua versi Excel
- Kolom K (Sangsi) di Rekapitulasi default 20 dan dapat diedit langsung di Excel
