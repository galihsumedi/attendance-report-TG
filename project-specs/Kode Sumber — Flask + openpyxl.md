# Kode Sumber — Flask + openpyxl

Kode lengkap untuk website pemrosesan laporan kehadiran karyawan.

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
├── uploads/               # Folder sementara upload (auto-dibuat)
└── output/                # Folder output (auto-dibuat)
```

---

## 1. `requirements.txt`

```
Flask==3.1.0
openpyxl==3.1.5
pandas==2.2.3
gunicorn
```

---

## 2. `app.py` — Aplikasi Utama Flask

```python
import os
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from processor import proses_data_scanlog
from excel_writer import buat_file_excel

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def ekstensi_valid(nama_file: str) -> bool:
    return '.' in nama_file and nama_file.rsplit('.', 1)[1].lower() == 'xlsx'


@app.route('/', methods=['GET'])
def halaman_utama():
    return render_template('index.html')


@app.route('/proses', methods=['POST'])
def proses_upload():
    if 'file' not in request.files:
        flash('Tidak ada file yang diunggah.', 'error')
        return redirect(url_for('halaman_utama'))

    file = request.files['file']
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('halaman_utama'))

    if not ekstensi_valid(file.filename):
        flash('Format file harus .xlsx', 'error')
        return redirect(url_for('halaman_utama'))

    nama_aman = secure_filename(file.filename)
    path_input = os.path.join(app.config['UPLOAD_FOLDER'], nama_aman)
    file.save(path_input)

    try:
        hasil = proses_data_scanlog(path_input)
        bulan_tahun = hasil['bulan_tahun_terdeteksi']

        nama_output = f"Laporan_Kehadiran_{bulan_tahun.replace(' ', '_')}.xlsx"
        path_output = os.path.join(app.config['OUTPUT_FOLDER'], nama_output)

        buat_file_excel(
            path_output=path_output,
            data_mentah=hasil['data_mentah'],
            rekapitulasi=hasil['rekapitulasi'],
            laporan_individual=hasil['laporan_individual'],
            bulan_tahun=bulan_tahun,
        )

        return send_file(
            path_output,
            as_attachment=True,
            download_name=nama_output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except ValueError as e:
        flash(f'Error validasi: {str(e)}', 'error')
        return redirect(url_for('halaman_utama'))
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
        return redirect(url_for('halaman_utama'))
    finally:
        if os.path.exists(path_input):
            os.remove(path_input)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

---

## 3. `processor.py` — Engine Pemrosesan Data

```python
from __future__ import annotations

import math
from datetime import datetime, time, timedelta
from calendar import monthrange
from typing import Any

import pandas as pd

JAM_MASUK_BATAS = time(8, 0, 0)
HARI_INDONESIA = {
    0: 'Sen', 1: 'Sel', 2: 'Rab',
    3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'
}


def validasi_dataframe(df: pd.DataFrame) -> None:
    kolom_wajib = ['PIN', 'NIP', 'Nama', 'Tanggal', 'Scan 1']
    kolom_hilang = [k for k in kolom_wajib if k not in df.columns]
    if kolom_hilang:
        raise ValueError(
            f"Kolom wajib tidak ditemukan: {', '.join(kolom_hilang)}. "
            f"Pastikan file mengandung kolom: {', '.join(kolom_wajib)}"
        )


def parse_waktu(nilai) -> time | None:
    if pd.isna(nilai) or nilai == '' or nilai is None:
        return None
    if isinstance(nilai, time):
        return nilai
    if isinstance(nilai, datetime):
        return nilai.time()
    try:
        return datetime.strptime(str(nilai).strip(), '%H:%M:%S').time()
    except ValueError:
        try:
            return datetime.strptime(str(nilai).strip(), '%H:%M').time()
        except ValueError:
            return None


def parse_tanggal(nilai) -> datetime | None:
    if pd.isna(nilai) or nilai is None:
        return None
    if isinstance(nilai, datetime):
        return nilai
    if isinstance(nilai, pd.Timestamp):
        return nilai.to_pydatetime()
    for fmt in ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
        try:
            return datetime.strptime(str(nilai).strip(), fmt)
        except ValueError:
            continue
    return None


def hitung_menit_terlambat(jam_masuk: time | None) -> int:
    if jam_masuk is None:
        return 0
    # Detik diabaikan — hanya jam dan menit yang dibandingkan.
    # 08:00:59 → 0 menit.  08:01:30 → 1 menit.  08:05:59 → 5 menit.
    menit_masuk = jam_masuk.hour * 60 + jam_masuk.minute
    menit_batas = 8 * 60  # 480
    if menit_masuk <= menit_batas:
        return 0
    return menit_masuk - menit_batas


def tentukan_catatan_otomatis(
    tanggal: datetime,
    scan1: time | None,
    scan2: time | None,
    scan3: time | None,
) -> str:
    hari = tanggal.weekday()
    if hari == 5:
        return 'Sabtu'
    if hari == 6:
        return 'Minggu'
    if scan1 is None and scan2 is None and scan3 is None:
        return 'Tidak ada scan'
    if scan1 is not None and scan2 is None and scan3 is None:
        return 'Hanya scan masuk'
    if scan3 is not None:
        return '3 scan terdeteksi'
    return ''


def proses_data_scanlog(path_file: str) -> dict[str, Any]:
    df = pd.read_excel(path_file, header=1)  # Header ada di baris ke-2
    df.columns = df.columns.str.strip()

    validasi_dataframe(df)

    duplikat = df.duplicated(subset=['PIN', 'Tanggal'], keep=False)
    if duplikat.any():
        jumlah_duplikat = duplikat.sum()
        raise ValueError(
            f"Ditemukan {jumlah_duplikat} baris duplikat (PIN + Tanggal sama). "
            f"Harap bersihkan data terlebih dahulu."
        )

    df['Tanggal_parsed'] = df['Tanggal'].apply(parse_tanggal)
    df['Scan1_parsed'] = df['Scan 1'].apply(parse_waktu)
    df['Scan2_parsed'] = df.get('Scan 2', pd.Series(dtype=object)).apply(parse_waktu)
    df['Scan3_parsed'] = df.get('Scan 3', pd.Series(dtype=object)).apply(parse_waktu)

    df = df.dropna(subset=['Tanggal_parsed'])

    if df.empty:
        raise ValueError("Tidak ada data valid setelah parsing tanggal.")

    bulan_nama = [
        '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]
    frekuensi = df['Tanggal_parsed'].dropna().apply(lambda d: (d.year, d.month)).value_counts()
    tahun, bulan = frekuensi.idxmax()
    bulan_tahun = f"{bulan_nama[bulan]} {tahun}"
    jumlah_hari = monthrange(tahun, bulan)[1]

    semua_tanggal = [
        datetime(tahun, bulan, d) for d in range(1, jumlah_hari + 1)
    ]

    karyawan_unik = (
        df.groupby('PIN')
        .first()[['NIP', 'Nama', 'Jabatan', 'Departemen', 'Kantor']]
        .reset_index()
    )

    rekapitulasi = []
    laporan_individual = {}

    for _, karyawan in karyawan_unik.iterrows():
        pin = karyawan['PIN']
        nama = karyawan['Nama']
        nip = karyawan.get('NIP', '')

        data_karyawan = df[df['PIN'] == pin].copy()

        scan_lookup = {}
        for _, row in data_karyawan.iterrows():
            tgl = row['Tanggal_parsed'].date()
            scan_lookup[tgl] = {
                'scan1': row['Scan1_parsed'],
                'scan2': row['Scan2_parsed'],
                'scan3': row['Scan3_parsed'],
            }

        detail_harian = []
        total_menit_terlambat = 0
        jumlah_hari_terlambat = 0

        for tgl in semua_tanggal:
            tgl_date = tgl.date()
            data_scan = scan_lookup.get(tgl_date, {
                'scan1': None, 'scan2': None, 'scan3': None
            })

            scan1 = data_scan['scan1']
            scan2 = data_scan['scan2']
            scan3 = data_scan['scan3']

            jam_keluar = scan3 if scan3 is not None else scan2

            # Tanggal 1 tidak dihitung keterlambatan — sering hanya berisi
            # scan keluar sisa shift malam bulan sebelumnya.
            if tgl.day == 1:
                menit_terlambat = 0
            else:
                menit_terlambat = hitung_menit_terlambat(scan1)

            jam_terlambat_str = ''
            if menit_terlambat > 0:
                total_menit_terlambat += menit_terlambat
                jumlah_hari_terlambat += 1
                jam_h = menit_terlambat // 60
                menit_m = menit_terlambat % 60
                if jam_h > 0:
                    jam_terlambat_str = f"{jam_h} jam {menit_m} menit"
                else:
                    jam_terlambat_str = f"{menit_m} menit"

            catatan_auto = tentukan_catatan_otomatis(tgl, scan1, scan2, scan3)
            hari_nama = HARI_INDONESIA[tgl.weekday()]

            detail_harian.append({
                'hari': hari_nama,
                'tanggal': tgl,
                'jam_kerja': '08:00-17:00',
                'jam_masuk': scan1,
                'jam_keluar': jam_keluar,
                'jam_terlambat': jam_terlambat_str,
                'menit_terlambat': menit_terlambat,
                'catatan_otomatis': catatan_auto,
                'catatan_manual': '',
                'is_weekend': tgl.weekday() >= 5,
            })

        laporan_individual[pin] = {
            'pin': pin,
            'nip': nip,
            'nama': nama,
            'detail': detail_harian,
        }

        rekapitulasi.append({
            'pin': pin,
            'nip': nip,
            'nama': nama,
            'jabatan': karyawan.get('Jabatan', ''),
            'departemen': karyawan.get('Departemen', ''),
            'kantor': karyawan.get('Kantor', ''),
            'jumlah_hari_terlambat': jumlah_hari_terlambat,
            'total_menit_terlambat': total_menit_terlambat,
        })

    rekapitulasi.sort(key=lambda x: x['pin'])

    return {
        'data_mentah': df.drop(
            columns=['Tanggal_parsed', 'Scan1_parsed', 'Scan2_parsed', 'Scan3_parsed'],
            errors='ignore'
        ),
        'rekapitulasi': rekapitulasi,
        'laporan_individual': laporan_individual,
        'bulan_tahun_terdeteksi': bulan_tahun,
    }
```

---

## 4. `excel_writer.py` — Generator File Excel Output

```python
from __future__ import annotations

from datetime import time
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

TNR = 'Times New Roman'

FONT_TITLE  = Font(name=TNR, bold=True, size=14)
FONT_HEADER = Font(name=TNR, bold=True, size=12)
FONT_NORMAL = Font(name=TNR, size=12)
FONT_MERAH  = Font(name=TNR, size=12, color='FF0000')
FONT_PILIH  = Font(name=TNR, bold=True, size=12, color='0070C0')

FILL_HEADER  = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
FILL_WEEKEND = PatternFill(start_color='DCE6F1', end_color='DCE6F1', fill_type='solid')
FILL_PILIH   = PatternFill(start_color='FFFFCC', end_color='FFFFCC', fill_type='solid')

THIN = Side(style='thin')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

ALIGN_C  = Alignment(horizontal='center', vertical='center', wrap_text=True)
ALIGN_L  = Alignment(horizontal='left',   vertical='center')
ALIGN_C0 = Alignment(horizontal='center', vertical='center')


def _header_cell(ws, coord, value):
    c = ws[coord]
    c.value = value
    c.font = FONT_HEADER
    c.fill = FILL_HEADER
    c.border = BORDER
    c.alignment = ALIGN_C
    return c


def format_waktu(t: time | None) -> str:
    return t.strftime('%H:%M:%S') if t else ''


# ---------------------------------------------------------------------------
# Sheet 1 — Data Mentah
# ---------------------------------------------------------------------------

def buat_sheet_data_mentah(wb: Workbook, data_mentah: pd.DataFrame) -> None:
    ws = wb.create_sheet(title='Data Mentah')

    for col_idx, col_name in enumerate(data_mentah.columns, 1):
        c = ws.cell(row=1, column=col_idx, value=col_name)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.border = BORDER
        c.alignment = ALIGN_C0

    for row_idx, row in enumerate(data_mentah.itertuples(index=False), 2):
        for col_idx, value in enumerate(row, 1):
            c = ws.cell(row=row_idx, column=col_idx)
            try:
                c.value = '' if pd.isna(value) else value
            except (TypeError, ValueError):
                c.value = value
            c.font = FONT_NORMAL
            c.border = BORDER

    for col_idx in range(1, len(data_mentah.columns) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 15


# ---------------------------------------------------------------------------
# Sheet 2 — Rekapitulasi
# ---------------------------------------------------------------------------

def buat_sheet_rekapitulasi(
    wb: Workbook,
    rekapitulasi: list[dict],
    bulan_tahun: str,
    rng_end: int,
) -> None:
    ws = wb.create_sheet(title='Rekapitulasi')

    # Title rows — row 1: company header, row 3: month (row 2 intentionally blank)
    for row, text in [
        (1, 'REKAPITULASI LAPORAN KEHADIRAN KARYAWAN TECTONA GROUP'),
        (3, f'BULAN {bulan_tahun.upper()}'),
    ]:
        ws.merge_cells(f'A{row}:M{row}')
        c = ws[f'A{row}']
        c.value = text
        c.font = FONT_TITLE
        c.alignment = ALIGN_C0

    # ---- Header rows 5–6 ----
    # Border must be set on BOTH anchor (row 5) and slave (row 6) cells so
    # the full outline appears — openpyxl reads the bottom border from row 6.
    span_two_rows = {
        'A': 'No',
        'B': 'Nama Karyawan',
        'C': 'Cuti',
        'D': 'Sakit',
        'E': 'Izin',
        'I': 'Jumlah\nDalam Menit',
        'K': 'Total',
        'M': 'Jumlah',
    }
    for kol, label in span_two_rows.items():
        ws[f'{kol}5'].value = label
        ws.merge_cells(f'{kol}5:{kol}6')
        c = ws[f'{kol}5']
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.border = BORDER
        c.alignment = ALIGN_C
        ws[f'{kol}6'].border = BORDER  # bottom border of merged area

    # F: "Dinas Lapangan" — single merged cell spanning rows 5–6 with wrap text
    ws['F5'].value = 'Dinas Lapangan'
    ws.merge_cells('F5:F6')
    c = ws['F5']
    c.font = FONT_HEADER
    c.fill = FILL_HEADER
    c.border = BORDER
    c.alignment = ALIGN_C
    ws['F6'].border = BORDER

    # G5:H5 merged — "Terlambat Masuk"; G6="Jam", H6="Menit"
    ws.merge_cells('G5:H5')
    _header_cell(ws, 'G5', 'Terlambat Masuk')
    ws['H5'].border = BORDER
    _header_cell(ws, 'G6', 'Jam')
    _header_cell(ws, 'H6', 'Menit')

    # J: Denda/Menit (row 5) / Rp. (row 6)
    _header_cell(ws, 'J5', 'Denda/Menit')
    _header_cell(ws, 'J6', 'Rp.')

    # L: Sangsi (row 5) / 20 X (row 6)
    _header_cell(ws, 'L5', 'Sangsi')
    _header_cell(ws, 'L6', '20 X')

    # ---- Data rows ----
    for idx, k in enumerate(rekapitulasi):
        r = 7 + idx
        static = [
            (1, idx + 1), (2, k['nama']),
            (3, None), (4, None), (5, None), (6, None),
            (10, None),  # J: Denda/Menit — user fills manually
        ]
        for col, val in static:
            c = ws.cell(row=r, column=col, value=val)
            c.font = FONT_NORMAL
            c.border = BORDER
            c.alignment = ALIGN_L if col == 2 else ALIGN_C0

        # I = SUMIF total lateness minutes from Data Harian col H
        c = ws.cell(row=r, column=9)
        c.value = (
            f"=SUMIF('Data Harian'!$A$2:$A${rng_end},"
            f"B{r},'Data Harian'!$H$2:$H${rng_end})"
        )
        c.font = FONT_NORMAL
        c.number_format = '#,##0'
        c.border = BORDER
        c.alignment = ALIGN_C0

        # G = full hours late
        c = ws.cell(row=r, column=7)
        c.value = f'=INT(I{r}/60)'
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # H = remaining minutes
        c = ws.cell(row=r, column=8)
        c.value = f'=MOD(I{r},60)'
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # K = Total (Jumlah Menit × Denda/Menit)
        c = ws.cell(row=r, column=11)
        c.value = f'=IF(AND(I{r}<>"",J{r}<>""),I{r}*J{r},"-")'
        c.font = FONT_NORMAL
        c.number_format = '#,##0'
        c.border = BORDER
        c.alignment = ALIGN_C0

        # L = Sangsi multiplier (default 20)
        c = ws.cell(row=r, column=12, value=20)
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # M = Jumlah Final (Total × Sangsi)
        c = ws.cell(row=r, column=13)
        c.value = f'=IF(AND(K{r}<>"-",K{r}<>""),K{r}*L{r},"-")'
        c.font = FONT_NORMAL
        c.number_format = '#,##0'
        c.border = BORDER
        c.alignment = ALIGN_C0

    lebar = {
        'A': 5, 'B': 28, 'C': 8, 'D': 8, 'E': 8, 'F': 12,
        'G': 8, 'H': 8, 'I': 16, 'J': 14, 'K': 14, 'L': 10, 'M': 14,
    }
    for kol, w in lebar.items():
        ws.column_dimensions[kol].width = w


# ---------------------------------------------------------------------------
# Sheet 4 — Data Harian (visible, user-editable)
# ---------------------------------------------------------------------------

def buat_sheet_data_harian(
    wb: Workbook,
    laporan_individual: dict[int, dict],
    daftar_nama: list[str],
) -> str:
    SHEET_NAME = 'Data Harian'
    ws = wb.create_sheet(title=SHEET_NAME)

    # Column layout (A–N):
    # A=Nama, B=NoHari, C=Hari, D=Tanggal, E=JamKerja, F=JamMasuk, G=JamKeluar,
    # H=MenitTerlambat(number for SUMIF), I=JamTerlambat(display string),
    # J=CatatanOtomatis, K=IsWeekend, L=PIN, M=Key, N=CatatanManual(user-editable)
    headers = [
        'Nama', 'No Hari', 'Hari', 'Tanggal', 'Jam Kerja',
        'Jam Masuk', 'Jam Keluar', 'Menit Terlambat', 'Jam Terlambat',
        'Catatan Otomatis', 'Is Weekend', 'PIN', 'Key', 'Catatan (Manual)',
    ]
    for col_idx, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col_idx, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.border = BORDER

    baris = 2
    for pin in sorted(laporan_individual.keys()):
        data = laporan_individual[pin]
        nama = data['nama']

        for idx_hari, d in enumerate(data['detail'], 1):
            ws.cell(row=baris, column=1,  value=nama)
            ws.cell(row=baris, column=2,  value=idx_hari)
            ws.cell(row=baris, column=3,  value=d['hari'])
            ws.cell(row=baris, column=4,  value=d['tanggal'].strftime('%d-%m-%Y'))
            ws.cell(row=baris, column=5,  value=d['jam_kerja'])
            ws.cell(row=baris, column=6,  value=format_waktu(d['jam_masuk']))
            ws.cell(row=baris, column=7,  value=format_waktu(d['jam_keluar']))
            ws.cell(row=baris, column=8,  value=d['menit_terlambat'])   # numeric
            ws.cell(row=baris, column=9,  value=d['jam_terlambat'])     # display string
            ws.cell(row=baris, column=10, value=d['catatan_otomatis'])
            ws.cell(row=baris, column=11, value=1 if d['is_weekend'] else 0)
            ws.cell(row=baris, column=12, value=data['pin'])
            ws.cell(row=baris, column=13, value=f"{nama}|{idx_hari}")  # lookup key
            ws.cell(row=baris, column=14, value='')                     # Catatan (Manual)

            for col in range(1, 15):
                ws.cell(row=baris, column=col).font = FONT_NORMAL
                ws.cell(row=baris, column=col).border = BORDER

            baris += 1

    # Auto-fit column widths based on max content length
    for col_idx, col_cells in enumerate(ws.columns, 1):
        max_len = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in col_cells
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 40)

    # Auto-filter on header row
    ws.auto_filter.ref = f'A1:{get_column_letter(14)}{baris - 1}'

    return SHEET_NAME


# ---------------------------------------------------------------------------
# Sheet 3 — Laporan Individual (lookup template)
# ---------------------------------------------------------------------------

def buat_sheet_individual_lookup(
    wb: Workbook,
    laporan_individual: dict[int, dict],
    daftar_nama: list[str],
    jumlah_hari_bulan: int,
    nama_sheet_helper: str,
) -> None:
    ws = wb.create_sheet(title='Laporan Individual')

    total_rows = sum(len(d['detail']) for d in laporan_individual.values())
    rng_end = total_rows + 1  # +1 for header row in Data Harian

    def rng(col: str) -> str:
        return f"'{nama_sheet_helper}'!${col}$2:${col}${rng_end}"

    # Key column M = "Nama|DayNum". Simple MATCH — no array formula needed,
    # works in all Excel versions.
    def lookup(helper_col: str, day: int) -> str:
        return (
            f'=IFERROR(INDEX({rng(helper_col)},'
            f'MATCH($C$6&"|"&{day},{rng("M")},0)),"")'
        )

    def weekend_flag(day: int) -> str:
        return (
            f'=IFERROR(INDEX({rng("K")},'
            f'MATCH($C$6&"|"&{day},{rng("M")},0)),0)'
        )

    # ---- Row 1: Warning ----
    ws.merge_cells('A1:H1')
    c = ws['A1']
    c.value = (
        'PERINGATAN: Sheet ini hanya untuk melihat laporan. '
        'Untuk mengisi Catatan (Manual), edit langsung di sheet "Data Harian".'
    )
    c.font = Font(name=TNR, bold=True, size=11, color='C00000')
    c.fill = PatternFill(start_color='FFE0E0', end_color='FFE0E0', fill_type='solid')
    c.alignment = ALIGN_C0

    # ---- Row 2: Title ----
    ws.merge_cells('A2:H2')
    c = ws['A2']
    c.value = 'LAPORAN KEHADIRAN KARYAWAN'
    c.font = FONT_TITLE
    c.alignment = ALIGN_C0

    # ---- Row 5: Fingerprint ID (auto-lookup) ----
    ws['A5'].value = 'Fingerprint ID'
    ws['A5'].font = FONT_HEADER
    ws['C5'].value = f'=IFERROR(INDEX({rng("L")},MATCH($C$6,{rng("A")},0)),"")'
    ws['C5'].font = FONT_NORMAL

    # ---- Row 6: Nama Karyawan dropdown ----
    ws['A6'].value = 'Nama Karyawan'
    ws['A6'].font = FONT_HEADER
    ws['C6'].value = daftar_nama[0] if daftar_nama else ''
    ws['C6'].font = FONT_PILIH
    ws['C6'].fill = FILL_PILIH
    ws['C6'].border = BORDER

    # Name list in hidden column J (dropdown source)
    for i, nama in enumerate(daftar_nama, 1):
        ws.cell(row=i, column=10, value=nama)
    ws.column_dimensions['J'].hidden = True

    dv = DataValidation(
        type='list',
        formula1=f'=$J$1:$J${len(daftar_nama)}',
        allow_blank=False,
    )
    dv.prompt = 'Pilih nama karyawan'
    dv.promptTitle = 'Nama Karyawan'
    dv.error = 'Pilih nama dari daftar yang tersedia.'
    dv.errorTitle = 'Nama Tidak Valid'
    ws.add_data_validation(dv)
    dv.add('C6')

    # ---- Rows 7–8: Double-row column headers ----
    col_labels = [
        ('A', 'Hari'), ('B', 'Tanggal'), ('C', 'Jam Kerja'),
        ('D', 'Jam Masuk'), ('E', 'Jam Keluar'), ('F', 'Jam Terlambat'),
        ('G', 'Catatan\n(Otomatis)'), ('H', 'Catatan\n(Manual)'),
    ]
    for kol, label in col_labels:
        ws.merge_cells(f'{kol}7:{kol}8')
        _header_cell(ws, f'{kol}7', label)
        ws[f'{kol}8'].border = BORDER

    # ---- Data rows 9 … (8 + days) ----
    # Mapping: sheet col → Data Harian col
    # C=Hari, D=Tanggal, E=JamKerja, F=JamMasuk, G=JamKeluar,
    # I=JamTerlambat(string), J=CatatanOtomatis, N=CatatanManual
    col_map = [
        ('A', 'C'), ('B', 'D'), ('C', 'E'), ('D', 'F'),
        ('E', 'G'), ('F', 'I'), ('G', 'J'), ('H', 'N'),
    ]

    for day in range(1, jumlah_hari_bulan + 1):
        r = 8 + day

        for sheet_col, helper_col in col_map:
            c = ws[f'{sheet_col}{r}']
            c.value = lookup(helper_col, day)
            c.font = FONT_NORMAL
            c.border = BORDER
            c.alignment = ALIGN_C0

        # I (hidden): weekend flag for conditional formatting
        ws[f'I{r}'].value = weekend_flag(day)

    ws.column_dimensions['I'].hidden = True

    # ---- Conditional formatting: highlight weekend rows ----
    r_data_start = 9
    r_data_end = 8 + jumlah_hari_bulan
    ws.conditional_formatting.add(
        f'A{r_data_start}:H{r_data_end}',
        FormulaRule(
            formula=[f'$I{r_data_start}=1'],
            fill=FILL_WEEKEND,
            font=FONT_MERAH,
        )
    )

    # ---- Column widths ----
    lebar = {
        'A': 7, 'B': 14, 'C': 14, 'D': 14,
        'E': 14, 'F': 17, 'G': 30, 'H': 30,
    }
    for kol, w in lebar.items():
        ws.column_dimensions[kol].width = w

    # ---- Sheet protection ----
    # Only C6 (dropdown) is unlocked. All other cells show a warning on edit.
    # Catatan (Manual) must be edited directly in the Data Harian sheet.
    from openpyxl.styles.protection import Protection
    ws['C6'].protection = Protection(locked=False)
    ws.protection.sheet = True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def buat_file_excel(
    path_output: str,
    data_mentah: pd.DataFrame,
    rekapitulasi: list[dict],
    laporan_individual: dict[int, dict],
    bulan_tahun: str,
) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    daftar_nama = [
        laporan_individual[pin]['nama']
        for pin in sorted(laporan_individual.keys())
    ]

    first_pin = sorted(laporan_individual.keys())[0]
    jumlah_hari_bulan = len(laporan_individual[first_pin]['detail'])
    total_baris_data = sum(len(d['detail']) for d in laporan_individual.values())
    rng_end = total_baris_data + 1  # +1 for Data Harian header row

    buat_sheet_data_mentah(wb, data_mentah)
    buat_sheet_rekapitulasi(wb, rekapitulasi, bulan_tahun, rng_end)
    helper_name = buat_sheet_data_harian(wb, laporan_individual, daftar_nama)
    buat_sheet_individual_lookup(
        wb, laporan_individual, daftar_nama,
        jumlah_hari_bulan, helper_name,
    )

    sheet_order = ['Data Mentah', 'Rekapitulasi', 'Laporan Individual', 'Data Harian']
    for i, name in enumerate(sheet_order):
        if name in wb.sheetnames:
            wb.move_sheet(name, offset=i - wb.sheetnames.index(name))

    wb.active = wb.sheetnames.index('Laporan Individual')
    wb.save(path_output)
```

---

## 5. `templates/index.html` — Halaman Upload

```html
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laporan Kehadiran Karyawan — Tectona Group</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }
        h1 { font-size: 1.5rem; color: #1a1a1a; margin-bottom: 8px; text-align: center; }
        .subtitle { color: #666; text-align: center; margin-bottom: 32px; font-size: 0.9rem; }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-weight: 600; margin-bottom: 6px; color: #333; font-size: 0.9rem; }
        .upload-area {
            border: 2px dashed #ccc;
            border-radius: 12px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: #fafafa;
        }
        .upload-area:hover { border-color: #4a90d9; background: #f0f7ff; }
        .upload-area.drag-over { border-color: #4a90d9; background: #e8f0fe; }
        .upload-area p { color: #666; margin-top: 8px; font-size: 0.85rem; }
        .upload-icon { font-size: 2.5rem; margin-bottom: 8px; }
        .file-name { color: #4a90d9; font-weight: 600; margin-top: 8px; }
        input[type="file"] { display: none; }
        button {
            width: 100%;
            padding: 12px;
            background: #2c5f2d;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 12px;
        }
        button:hover { background: #1e4620; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .flash-messages { margin-bottom: 20px; }
        .flash { padding: 12px 16px; border-radius: 8px; font-size: 0.85rem; margin-bottom: 8px; }
        .flash.error { background: #fdecea; color: #c62828; border: 1px solid #f5c6cb; }
        .flash.success { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>&#128203; Laporan Kehadiran</h1>
        <p class="subtitle">Tectona Group — Proses Data Absensi Fingerprint</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash {{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <form method="POST" action="/proses" enctype="multipart/form-data" id="uploadForm">
            <div class="form-group">
                <label>File Scanlog (.xlsx)</label>
                <div class="upload-area" id="dropZone" onclick="document.getElementById('fileInput').click()">
                    <div class="upload-icon">&#128193;</div>
                    <div>Klik atau seret file ke sini</div>
                    <p>Format: .xlsx — Maks 16MB</p>
                    <div class="file-name" id="fileName"></div>
                </div>
                <input type="file" name="file" id="fileInput" accept=".xlsx" required>
            </div>

            <button type="submit" id="submitBtn">Proses &amp; Download Laporan</button>
        </form>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const submitBtn = document.getElementById('submitBtn');

        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                fileName.textContent = '✅ ' + this.files[0].name;
            }
        });

        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                fileName.textContent = '✅ ' + e.dataTransfer.files[0].name;
            }
        });

        document.getElementById('uploadForm').addEventListener('submit', function() {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Memproses...';
        });
    </script>
</body>
</html>
```

---

## Cara Menjalankan

### 1. Instalasi

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# atau: venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Jalankan Server

```bash
python app.py
```

Buka browser di `http://localhost:5000`

### 3. Deploy ke Render

1. Push kode ke GitHub
2. Buat akun di [render.com](https://render.com)
3. New → Web Service → hubungkan repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
