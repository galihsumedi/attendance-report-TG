"""
Recalculates menit_terlambat for a single attendance_day row.

Two independent controls on attendance_days:
  - adj_absen           → only affects HK Tdk Scan count (noscan), never lateness
  - adj_keterlambatan   → controls whether lateness is zeroed or recalculated
      'koreksi_scan'      → recalculate from adj_jam_masuk
      any other value     → zero lateness (excuse granted)
      empty string        → calculate from adj_jam_masuk or raw_scan1
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, time

from models import get_attendance_day, update_attendance_day, get_setting

ZERO_LATENESS_TYPES = {'cuaca', 'dinas_lapangan', 'keterlambatan_disetujui', 'koreksi_scan', 'cuaca_banjir', 'cuti_bersama'}


def _parse_time(s: str | None) -> time | None:
    if not s:
        return None
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _calc_from_time(jam_masuk: time | None, grace: int) -> int:
    if jam_masuk is None:
        return 0
    menit_masuk = jam_masuk.hour * 60 + jam_masuk.minute
    raw_late = max(0, menit_masuk - 480)  # 480 = 8 * 60
    return max(0, raw_late - grace)


def hitung_ulang(conn: sqlite3.Connection, day_id: int) -> int:
    """Recalculates and saves menit_terlambat. Returns new value."""
    day = get_attendance_day(conn, day_id)
    if not day:
        return 0

    # Non-workdays and day-1 exemption always zero
    if day['is_day1_exempt'] or day['is_weekend'] or day['is_holiday']:
        menit = 0
    else:
        adj_ket = day['adj_keterlambatan'] or ''

        if adj_ket in ZERO_LATENESS_TYPES:
            menit = 0
        else:
            grace = int(get_setting(conn, 'grace_period_menit', '0') or '0')
            jam_masuk_str = day['adj_jam_masuk'] or day['raw_scan1']
            menit = _calc_from_time(_parse_time(jam_masuk_str), grace)

    update_attendance_day(conn, day_id, {'menit_terlambat': menit})
    return menit


def hitung_semua(conn: sqlite3.Connection, period_id: int) -> None:
    rows = conn.execute(
        'SELECT id FROM attendance_days WHERE period_id = ?', (period_id,)
    ).fetchall()
    for row in rows:
        hitung_ulang(conn, row['id'])
