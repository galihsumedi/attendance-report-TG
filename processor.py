from __future__ import annotations

import json
import logging
import math
import urllib.request
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from typing import Any

import pandas as pd

from nama_karyawan import NAMA_LENGKAP

_CACHE_LIBUR: dict[int, dict[date, str]] = {}


def ambil_hari_libur_nasional(year: int) -> dict[date, str]:
    if year in _CACHE_LIBUR:
        return _CACHE_LIBUR[year]
    try:
        url = f'https://date.nager.at/api/v3/PublicHolidays/{year}/ID'
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                raise ValueError(f'HTTP {resp.status}')
            data = json.loads(resp.read().decode())
        result = {
            datetime.strptime(item['date'], '%Y-%m-%d').date(): item['localName']
            for item in data
        }
        _CACHE_LIBUR[year] = result
        return result
    except Exception as e:
        logging.warning(f'Gagal mengambil data hari libur nasional: {e}. Laporan dibuat tanpa penandaan hari libur.')
        _CACHE_LIBUR[year] = {}
        return {}

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
    # Compare using only hour+minute (seconds are ignored).
    # 08:00:59 → 0 minutes late.  08:01:30 → 1 minute late.  08:05:59 → 5 minutes late.
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
    nama_libur: str | None = None,
) -> str:
    hari = tanggal.weekday()
    if hari == 5:
        return 'Sabtu'
    if hari == 6:
        return 'Minggu'
    if nama_libur:
        return nama_libur
    if scan1 is None and scan2 is None and scan3 is None:
        return 'Tidak ada scan'
    if scan1 is not None and scan2 is None and scan3 is None:
        return 'Hanya scan masuk'
    if scan3 is not None:
        return '3 scan terdeteksi'
    return ''


# Night-shift pairing tolerances. A real shift runs ~8-9h; rest between
# shifts runs ~14-16h. We classify the gap between two consecutive scans:
# a gap within [MIN_SHIFT, MAX_SHIFT] is a worked shift (masuk -> keluar);
# anything larger is rest, anything smaller is a double/ambiguous scan.
SHIFT_MALAM_MIN = timedelta(hours=3)
SHIFT_MALAM_MAX = timedelta(hours=13)

FLAG_TANPA_KELUAR = 'Scan keluar tidak ada'
FLAG_TANPA_MASUK = 'Scan masuk tidak ada'
FLAG_AMBIGU = 'Scan ganda/ambigu'
FLAG_MULTI = 'Beberapa shift dalam 1 hari'


def pasangkan_shift_malam(
    scans: list[datetime],
    tahun: int,
    bulan: int,
) -> dict[date, dict[str, Any]]:
    """
    Pair clock-in/clock-out scans for a night-shift employee whose shifts
    cross midnight. Works on the full chronological scan stream (including
    boundary rows from the adjacent months) and attributes each shift to the
    date it STARTS. Returns {start_date: {masuk, keluar, flag}} restricted to
    the target month. masuk/keluar are time objects (or None). flag is a
    human-readable note for incomplete/ambiguous days ('' when clean).
    """
    ev = sorted(set(scans))
    n = len(ev)
    entries: list[tuple[date, time | None, time | None, str]] = []

    i = 0
    while i < n:
        cur = ev[i]
        nxt = ev[i + 1] if i + 1 < n else None
        gap_next = (nxt - cur) if nxt is not None else None

        if gap_next is not None and SHIFT_MALAM_MIN <= gap_next <= SHIFT_MALAM_MAX:
            # cur = masuk, nxt = keluar; attribute to the start date
            entries.append((cur.date(), cur.time(), nxt.time(), ''))
            i += 2
            continue

        # Lone scan that doesn't pair cleanly with the next one.
        if gap_next is not None and gap_next < SHIFT_MALAM_MIN:
            # Two scans too close together to be a real shift (double tap).
            entries.append((cur.date(), cur.time(), None, FLAG_AMBIGU))
        elif cur.time().hour < 12:
            # Lone early-morning scan = exit of a shift whose entry is missing
            # or belongs to the previous month.
            entries.append((cur.date(), None, cur.time(), FLAG_TANPA_MASUK))
        else:
            # Lone afternoon/evening scan = entry with no recorded exit.
            entries.append((cur.date(), cur.time(), None, FLAG_TANPA_KELUAR))
        i += 1

    result: dict[date, dict[str, Any]] = {}
    for d, masuk, keluar, flag in entries:
        if d.month != bulan or d.year != tahun:
            continue
        if d in result:
            prev = result[d]
            flags = [f for f in (prev['flag'], FLAG_MULTI) if f]
            result[d] = {
                'masuk': prev['masuk'] or masuk,
                'keluar': prev['keluar'] or keluar,
                'flag': ' | '.join(flags),
            }
        else:
            result[d] = {'masuk': masuk, 'keluar': keluar, 'flag': flag}
    return result


def proses_data_scanlog(path_file: str) -> dict[str, Any]:
    df = pd.read_excel(path_file, header=1)
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
        nama = NAMA_LENGKAP.get(karyawan['Nama'], karyawan['Nama'])
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

        libur = ambil_hari_libur_nasional(tahun)

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

            # Day 1 of the month often carries only an exit scan from the
            # previous period, so lateness is never charged on that day.
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

            is_weekend = tgl.weekday() >= 5
            is_holiday = tgl_date in libur and not is_weekend
            nama_libur = libur.get(tgl_date) if is_holiday else None
            catatan_auto = tentukan_catatan_otomatis(tgl, scan1, scan2, scan3, nama_libur)
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
                'is_weekend': is_weekend,
                'is_holiday': is_holiday,
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
