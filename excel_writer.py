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
    # Columns that merge rows 5+6 into a single label.
    # Border must be set on BOTH anchor (row 5) and slave (row 6) cells so the
    # full outline appears — openpyxl only reads the bottom border from row 6.
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
    c.alignment = ALIGN_C          # ALIGN_C has wrap_text=True
    ws['F6'].border = BORDER       # bottom border of merged area

    # G5:H5 merged — "Terlambat Masuk"
    ws.merge_cells('G5:H5')
    _header_cell(ws, 'G5', 'Terlambat Masuk')
    ws['H5'].border = BORDER  # slave cell still needs border
    _header_cell(ws, 'G6', 'Jam')
    _header_cell(ws, 'H6', 'Menit')

    # J: two-row label (Denda/Menit / Rp.), not merged
    _header_cell(ws, 'J5', 'Denda/Menit')
    _header_cell(ws, 'J6', 'Rp.')

    # L: two-row label (Sangsi / 20 X), not merged
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

        # G = full hours late  (INT(total_minutes / 60))
        c = ws.cell(row=r, column=7)
        c.value = f'=INT(I{r}/60)'
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # H = remaining minutes  (MOD(total_minutes, 60))
        c = ws.cell(row=r, column=8)
        c.value = f'=MOD(I{r},60)'
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # K = Total (formula)
        c = ws.cell(row=r, column=11)
        c.value = f'=IF(AND(I{r}<>"",J{r}<>""),I{r}*J{r},"-")'
        c.font = FONT_NORMAL
        c.number_format = '#,##0'
        c.border = BORDER
        c.alignment = ALIGN_C0

        # L = Sangsi multiplier
        c = ws.cell(row=r, column=12, value=20)
        c.font = FONT_NORMAL
        c.border = BORDER
        c.alignment = ALIGN_C0

        # M = Jumlah (formula)
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
# Sheet 4 (hidden) — Data Harian
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
    # H=MenitTerlambat(number), I=JamTerlambat(string), J=CatatanOtomatis,
    # K=IsWeekend, L=PIN, M=Key, N=CatatanManual(user-editable)
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
            ws.cell(row=baris, column=8,  value=d['menit_terlambat'])   # numeric for SUMIF
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

    # Key column is M ("Nama|DayNum"). Simple single-criteria MATCH —
    # no array formula needed, works in all Excel versions.
    def lookup(helper_col: str, day: int) -> str:
        return (
            f'=IFERROR(INDEX({rng(helper_col)},'
            f'MATCH($C$6&"|"&{day},{rng("M")},0)),"")'
        )

    def weekend_flag(day: int) -> str:
        # K = Is Weekend column in Data Harian
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

    # ---- Row 5: Fingerprint ID ----
    ws['A5'].value = 'Fingerprint ID'
    ws['A5'].font = FONT_HEADER
    # Simple MATCH: every row for this employee has the same PIN, first match is fine
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

    # ---- Rows 7–8: Double-row column headers (matching reference style) ----
    col_labels = [
        ('A', 'Hari'), ('B', 'Tanggal'), ('C', 'Jam Kerja'),
        ('D', 'Jam Masuk'), ('E', 'Jam Keluar'), ('F', 'Jam Terlambat'),
        ('G', 'Catatan\n(Otomatis)'), ('H', 'Catatan\n(Manual)'),
    ]
    for kol, label in col_labels:
        ws.merge_cells(f'{kol}7:{kol}8')
        _header_cell(ws, f'{kol}7', label)
        ws[f'{kol}8'].border = BORDER  # slave row border

    # ---- Data rows 9 … (8 + days) ----
    # Data Harian column mapping (A–H in Laporan Individual → columns in Data Harian):
    #   C=Hari, D=Tanggal, E=JamKerja, F=JamMasuk, G=JamKeluar,
    #   I=JamTerlambat(display string), J=CatatanOtomatis, N=CatatanManual
    col_map = [
        ('A', 'C'), ('B', 'D'), ('C', 'E'), ('D', 'F'),
        ('E', 'G'), ('F', 'I'), ('G', 'J'), ('H', 'N'),
    ]

    for day in range(1, jumlah_hari_bulan + 1):
        r = 8 + day  # rows 9, 10, ...

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
    # Unlock only C6 (name dropdown) so users cannot accidentally overwrite
    # formulas. Catatan (Manual) must be edited in the Data Harian sheet.
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
