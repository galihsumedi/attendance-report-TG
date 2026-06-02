"""
Wraps processor.py: reads a scanlog, resolves employee names via the DB,
and persists rows into attendance_days.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

import nama_karyawan
import processor
from models import (
    build_nama_lengkap_map,
    get_employee_by_alias,
    create_employee,
    add_alias,
    upsert_period,
    upsert_attendance_day,
)

NIGHT_SHIFT_TYPE = 'keamanan_malam'


def _scan_datetimes_for_pin(data_mentah: pd.DataFrame, pin) -> list[datetime]:
    """Collect every scan (Scan 1/2/3, all dates incl. boundary months) for a
    PIN as chronological datetimes, for night-shift pairing."""
    sub = data_mentah[data_mentah['PIN'] == pin]
    out: list[datetime] = []
    for _, r in sub.iterrows():
        tgl = processor.parse_tanggal(r.get('Tanggal'))
        if tgl is None:
            continue
        for col in ('Scan 1', 'Scan 2', 'Scan 3'):
            t = processor.parse_waktu(r.get(col))
            if t is not None:
                out.append(datetime.combine(tgl.date(), t))
    return out


def _safe_str(v) -> str:
    """Convert a value to str, treating None and NaN as empty string."""
    if v is None:
        return ''
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return ''
    except Exception:
        pass
    return str(v).strip()


def _read_fingerprint_names(path_file: str) -> list[str]:
    df = pd.read_excel(path_file, header=1)
    df.columns = df.columns.str.strip()
    if 'Nama' not in df.columns:
        return []
    return df['Nama'].dropna().unique().tolist()


def get_unknown_aliases(conn: sqlite3.Connection, path_file: str) -> tuple[list[str], dict]:
    """
    Returns (unknown_aliases, preflight_info).
    unknown_aliases: fingerprint names not yet in employee_aliases.
    preflight_info: {bulan_tahun, jumlah_karyawan, jumlah_record}
    """
    known_map = build_nama_lengkap_map(conn)

    # Read the file for pre-flight stats without full processing
    df = pd.read_excel(path_file, header=1)
    df.columns = df.columns.str.strip()

    jumlah_record = len(df)
    jumlah_karyawan = df['PIN'].nunique() if 'PIN' in df.columns else 0

    # Detect month using processor's parse logic
    nama_bulan = [
        '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]
    bulan_tahun = ''
    if 'Tanggal' in df.columns:
        tanggal_parsed = df['Tanggal'].apply(processor.parse_tanggal).dropna()
        if not tanggal_parsed.empty:
            frekuensi = tanggal_parsed.apply(lambda d: (d.year, d.month)).value_counts()
            tahun, bulan = frekuensi.idxmax()
            bulan_tahun = f"{nama_bulan[bulan]} {tahun}"

    fingerprint_names = _read_fingerprint_names(path_file)
    unknown = [n for n in fingerprint_names if n not in known_map]

    return unknown, {
        'bulan_tahun': bulan_tahun,
        'jumlah_karyawan': jumlah_karyawan,
        'jumlah_record': jumlah_record,
    }


def parse_and_persist(
    conn: sqlite3.Connection,
    path_file: str,
    resolve_map: dict[str, int],  # {alias -> employee_id} for newly resolved names
) -> dict:
    """
    Runs proses_data_scanlog() with an up-to-date NAMA_LENGKAP, then writes
    all rows into attendance_days. Returns period info.
    """
    # Sync NAMA_LENGKAP from DB so processor.py uses current names
    current_map = build_nama_lengkap_map(conn)

    # Add newly resolved names to DB first
    for alias, emp_id in resolve_map.items():
        emp = conn.execute('SELECT nama_lengkap FROM employees WHERE id = ?', (emp_id,)).fetchone()
        if emp:
            current_map[alias] = emp['nama_lengkap']

    # Mutate the shared dict so processor.py picks it up
    nama_karyawan.NAMA_LENGKAP.clear()
    nama_karyawan.NAMA_LENGKAP.update(current_map)

    hasil = processor.proses_data_scanlog(path_file)
    bulan_tahun = hasil['bulan_tahun_terdeteksi']

    # Derive bulan/tahun from bulan_tahun string
    nama_bulan = [
        '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]
    parts = bulan_tahun.split()
    bulan = nama_bulan.index(parts[0])
    tahun = int(parts[1])

    import os
    source_file = os.path.basename(path_file)
    period_id = upsert_period(conn, bulan, tahun, bulan_tahun, source_file)

    # Persist each employee's daily records
    rekapitulasi = hasil['rekapitulasi']
    laporan = hasil['laporan_individual']

    for k in rekapitulasi:
        pin = k['pin']
        nama = k['nama']

        # Ensure employee exists in DB (they may have been resolved via resolve_map)
        emp_row = conn.execute(
            '''SELECT e.id FROM employees e
               JOIN employee_aliases a ON a.employee_id = e.id
               WHERE e.nama_lengkap = ? OR a.alias = ?''',
            (nama, str(pin)),
        ).fetchone()

        if not emp_row:
            # Create employee with full name; alias = fingerprint name from scanlog
            fingerprint_alias = next(
                (alias for alias, full in current_map.items() if full == nama),
                nama,
            )
            emp_id = create_employee(conn, nama)
            try:
                add_alias(conn, emp_id, fingerprint_alias)
            except Exception:
                pass
        else:
            emp_id = emp_row['id']

        # Night-shift staff need shift pairing across midnight; the day-shift
        # detail (scan1=masuk, scan2=keluar) is wrong for them.
        emp_type_row = conn.execute(
            'SELECT employee_type FROM employees WHERE id = ?', (emp_id,)
        ).fetchone()
        is_night = bool(emp_type_row) and emp_type_row['employee_type'] == NIGHT_SHIFT_TYPE
        shift_map: dict = {}
        if is_night:
            scans = _scan_datetimes_for_pin(hasil['data_mentah'], pin)
            shift_map = processor.pasangkan_shift_malam(scans, tahun, bulan)

        detail = laporan[pin]['detail']
        for d in detail:
            tgl_str = d['tanggal'].strftime('%Y-%m-%d')
            catatan = d['catatan_otomatis']
            if is_night:
                shift = shift_map.get(d['tanggal'].date())
                masuk = shift['masuk'] if shift else None
                keluar = shift['keluar'] if shift else None
                scan1_str = masuk.strftime('%H:%M:%S') if masuk else None
                scan_out_str = keluar.strftime('%H:%M:%S') if keluar else None
                catatan = shift['flag'] if shift else ''
            else:
                scan1_str = d['jam_masuk'].strftime('%H:%M:%S') if d['jam_masuk'] else None
                scan_out = d['jam_keluar']
                scan_out_str = scan_out.strftime('%H:%M:%S') if scan_out else None

            row = {
                'pin': _safe_str(pin),
                'nama': _safe_str(nama),
                'tanggal': tgl_str,
                'raw_scan1': scan1_str,
                'raw_scan2': scan_out_str,  # processor merges scan2/scan3 → jam_keluar
                'raw_scan3': None,
                'menit_terlambat': d['menit_terlambat'],
                'status_hari': catatan,
                'catatan_otomatis': catatan,
                'is_weekend': 1 if d['is_weekend'] else 0,
                'is_holiday': 1 if d.get('is_holiday', False) else 0,
                'nama_libur': d.get('nama_libur'),
                'is_day1_exempt': 1 if d['tanggal'].day == 1 else 0,
                'jabatan': _safe_str(k.get('jabatan', '')),
                'departemen': _safe_str(k.get('departemen', '')),
                'kantor': _safe_str(k.get('kantor', '')),
                'nip': _safe_str(k.get('nip', '')),
            }
            upsert_attendance_day(conn, period_id, emp_id, row)

    conn.commit()

    return {
        'period_id': period_id,
        'bulan_tahun': bulan_tahun,
        'jumlah_karyawan': len(rekapitulasi),
    }
