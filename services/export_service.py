"""
Reads attendance data from the DB and reconstructs the structures that
excel_writer.buat_file_excel() expects, then calls it.
"""
from __future__ import annotations

import sqlite3
from calendar import monthrange
from datetime import datetime, time

import pandas as pd

from models import (
    get_period,
    get_attendance_days,
    get_period_employees,
    get_adjustments_for_period,
    get_setting,
)
from excel_writer import buat_file_excel, buat_sheet_log_penyesuaian
from openpyxl import load_workbook


def _str_to_time(s: str | None) -> time | None:
    if not s:
        return None
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _format_menit(menit: int) -> str:
    if menit <= 0:
        return ''
    jam_h = menit // 60
    menit_m = menit % 60
    if jam_h > 0:
        return f'{jam_h} jam {menit_m} menit'
    return f'{menit_m} menit'


HARI_INDONESIA = {
    0: 'Sen', 1: 'Sel', 2: 'Rab',
    3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min',
}


def buat_excel_dari_db(
    conn: sqlite3.Connection,
    period_id: int,
    path_output: str,
) -> str:
    period = get_period(conn, period_id)
    if not period:
        raise ValueError(f'Periode {period_id} tidak ditemukan.')

    bulan_tahun = period['bulan_tahun']
    bulan = period['bulan']
    tahun = period['tahun']
    jumlah_hari = monthrange(tahun, bulan)[1]

    days = get_attendance_days(conn, period_id)
    employees = get_period_employees(conn, period_id)

    # Build laporan_individual and rekapitulasi from DB rows
    laporan_individual: dict[str, dict] = {}
    rekapitulasi_map: dict[str, dict] = {}

    # Build employee attribute lookups from DB
    emp_type_map: dict[int, str] = {}
    emp_denda_map: dict[int, float] = {}
    for row in conn.execute('SELECT id, employee_type, denda_per_menit FROM employees').fetchall():
        emp_type_map[row['id']] = row['employee_type']
        emp_denda_map[row['id']] = row['denda_per_menit'] or 0

    for emp in employees:
        pin = emp['pin']
        nama = emp['nama']
        emp_type = emp_type_map.get(emp['employee_id'], 'standard')
        denda = emp_denda_map.get(emp['employee_id'], 0)
        laporan_individual[pin] = {
            'pin': pin,
            'nip': emp['nip'],
            'nama': nama,
            'employee_type': emp_type,
            'detail': [],
            'count_cuti': 0,
            'count_sakit': 0,
            'count_izin': 0,
            'count_dinas': 0,
            'hok': 0,
        }
        rekapitulasi_map[pin] = {
            'pin': pin,
            'nip': emp['nip'],
            'nama': nama,
            'jabatan': emp['jabatan'],
            'departemen': emp['departemen'],
            'kantor': emp['kantor'],
            'employee_type': emp_type,
            'denda_per_menit': denda,
            'jumlah_hari_terlambat': 0,
            'total_menit_terlambat': 0,
            'hok': 0,
        }

    # Index days by (pin, tanggal)
    day_index: dict[tuple, sqlite3.Row] = {}
    for d in days:
        day_index[(d['pin'], d['tanggal'])] = d

    # Build full calendar for the period
    all_dates = [datetime(tahun, bulan, day) for day in range(1, jumlah_hari + 1)]

    for pin in sorted(laporan_individual.keys(), key=lambda p: laporan_individual[p]['nama'].upper()):
        emp_type = laporan_individual[pin]['employee_type']
        is_keamanan = emp_type == 'keamanan'
        detail_list = []
        for tgl in all_dates:
            tgl_str = tgl.strftime('%Y-%m-%d')
            d = day_index.get((pin, tgl_str))

            if d:
                jam_masuk = _str_to_time(d['adj_jam_masuk'] or d['raw_scan1'])
                jam_keluar = _str_to_time(d['adj_jam_keluar'] or d['raw_scan2'])
                menit_terlambat = 0 if is_keamanan else d['menit_terlambat']
                catatan_otomatis = d['catatan_otomatis']
                catatan_manual = d['catatan_manual'] or ''
                is_weekend = bool(d['is_weekend'])
                is_holiday = bool(d['is_holiday'])
                nama_libur = d['nama_libur']
                adj_ket = d['adj_keterlambatan'] or ''
                adj_abs = d['adj_absen'] or ''
            else:
                jam_masuk = None
                jam_keluar = None
                menit_terlambat = 0
                catatan_otomatis = ''
                catatan_manual = ''
                is_weekend = tgl.weekday() >= 5
                is_holiday = False
                nama_libur = None
                adj_ket = ''
                adj_abs = ''

            # HOK: count days with any scan for security staff
            if is_keamanan and jam_masuk is not None:
                laporan_individual[pin]['hok'] += 1

            # Accumulate absence counts (workdays only, standard employees)
            if not is_keamanan and not is_weekend and not is_holiday:
                if adj_abs in ('cuti', 'cuti_bersama') or adj_ket == 'cuti_bersama':
                    laporan_individual[pin]['count_cuti'] += 1
                elif adj_abs == 'sakit':
                    laporan_individual[pin]['count_sakit'] += 1
                elif adj_abs == 'izin':
                    laporan_individual[pin]['count_izin'] += 1
                if adj_ket == 'dinas_lapangan':
                    laporan_individual[pin]['count_dinas'] += 1

            # Build catatan: combine auto + adj labels
            catatan_parts = [catatan_otomatis] if catatan_otomatis else []
            ADJ_ABS_LABEL = {
                'cuti': 'Cuti', 'izin': 'Izin', 'sakit': 'Sakit',
                'koreksi_scan': 'Koreksi Scan', 'cuti_bersama': 'Cuti Bersama',
            }
            ADJ_KET_LABEL = {
                'cuaca': 'Cuaca', 'dinas_lapangan': 'Dinas Lapangan',
                'keterlambatan_disetujui': 'Keterlambatan Disetujui',
                'koreksi_scan': 'Koreksi Scan', 'cuaca_banjir': 'Cuaca/Banjir',
            }
            if adj_abs and adj_abs in ADJ_ABS_LABEL:
                catatan_parts.append(ADJ_ABS_LABEL[adj_abs])
            if adj_ket and adj_ket in ADJ_KET_LABEL and adj_ket != adj_abs:
                catatan_parts.append(ADJ_KET_LABEL[adj_ket])
            if catatan_manual:
                catatan_parts.append(catatan_manual)
            catatan_gabung = ' | '.join(catatan_parts)

            jam_terlambat_str = _format_menit(menit_terlambat)

            if not is_keamanan and menit_terlambat > 0:
                rekapitulasi_map[pin]['total_menit_terlambat'] += menit_terlambat
                rekapitulasi_map[pin]['jumlah_hari_terlambat'] += 1

            detail_list.append({
                'hari': HARI_INDONESIA[tgl.weekday()],
                'tanggal': tgl,
                'jam_kerja': '8 Jam' if is_keamanan else '08:00-17:00',
                'jam_masuk': jam_masuk,
                'jam_keluar': jam_keluar,
                'jam_terlambat': jam_terlambat_str,
                'menit_terlambat': menit_terlambat,
                'catatan_otomatis': catatan_gabung,
                'catatan_manual': catatan_manual,
                'is_weekend': is_weekend,
                'is_holiday': is_holiday,
                'nama_libur': nama_libur,
            })

        laporan_individual[pin]['detail'] = detail_list
        rekapitulasi_map[pin]['hok'] = laporan_individual[pin]['hok']

    rekapitulasi = sorted(rekapitulasi_map.values(), key=lambda x: x['nama'].upper())

    # Build data_mentah — reconstruct from raw scan columns
    raw_rows = []
    for d in days:
        raw_rows.append({
            'PIN': d['pin'],
            'NIP': d['nip'],
            'Nama': d['nama'],
            'Tanggal': d['tanggal'],
            'Scan 1': d['raw_scan1'] or '',
            'Scan 2': d['raw_scan2'] or '',
            'Jabatan': d['jabatan'],
            'Departemen': d['departemen'],
            'Kantor': d['kantor'],
        })
    data_mentah = pd.DataFrame(raw_rows) if raw_rows else pd.DataFrame()

    buat_file_excel(
        path_output=path_output,
        data_mentah=data_mentah,
        rekapitulasi=rekapitulasi,
        laporan_individual=laporan_individual,
        bulan_tahun=bulan_tahun,
    )

    # Append Log Penyesuaian sheet
    adjustments = get_adjustments_for_period(conn, period_id)
    if adjustments:
        wb = load_workbook(path_output)
        buat_sheet_log_penyesuaian(wb, adjustments)
        wb.save(path_output)

    return path_output
