from __future__ import annotations

import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Employees & aliases
# ---------------------------------------------------------------------------

def get_all_employees(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        'SELECT * FROM employees ORDER BY nama_lengkap'
    ).fetchall()


def get_employee(conn: sqlite3.Connection, employee_id: int) -> sqlite3.Row | None:
    return conn.execute(
        'SELECT * FROM employees WHERE id = ?', (employee_id,)
    ).fetchone()


def get_employee_by_alias(conn: sqlite3.Connection, alias: str) -> sqlite3.Row | None:
    return conn.execute(
        '''SELECT e.* FROM employees e
           JOIN employee_aliases a ON a.employee_id = e.id
           WHERE a.alias = ?''',
        (alias,),
    ).fetchone()


def get_aliases_for_employee(conn: sqlite3.Connection, employee_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        'SELECT * FROM employee_aliases WHERE employee_id = ? ORDER BY alias',
        (employee_id,),
    ).fetchall()


def create_employee(conn: sqlite3.Connection, nama_lengkap: str) -> int:
    cur = conn.execute(
        'INSERT INTO employees (nama_lengkap) VALUES (?)', (nama_lengkap,)
    )
    conn.commit()
    return cur.lastrowid


def update_employee(conn: sqlite3.Connection, employee_id: int, nama_lengkap: str) -> None:
    conn.execute(
        "UPDATE employees SET nama_lengkap = ?, updated_at = datetime('now') WHERE id = ?",
        (nama_lengkap, employee_id),
    )
    conn.commit()


def delete_employee(conn: sqlite3.Connection, employee_id: int) -> None:
    conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
    conn.commit()


def add_alias(conn: sqlite3.Connection, employee_id: int, alias: str) -> int:
    cur = conn.execute(
        'INSERT INTO employee_aliases (employee_id, alias) VALUES (?, ?)',
        (employee_id, alias),
    )
    conn.commit()
    return cur.lastrowid


def delete_alias(conn: sqlite3.Connection, alias_id: int) -> None:
    conn.execute('DELETE FROM employee_aliases WHERE id = ?', (alias_id,))
    conn.commit()


def get_all_aliases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        '''SELECT a.id, a.alias, a.employee_id, e.nama_lengkap
           FROM employee_aliases a JOIN employees e ON e.id = a.employee_id
           ORDER BY a.alias'''
    ).fetchall()


def build_nama_lengkap_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {alias: nama_lengkap} for all registered aliases."""
    rows = conn.execute(
        'SELECT a.alias, e.nama_lengkap FROM employee_aliases a JOIN employees e ON e.id = a.employee_id'
    ).fetchall()
    return {r['alias']: r['nama_lengkap'] for r in rows}


def autocomplete_employees(conn: sqlite3.Connection, q: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, nama_lengkap FROM employees WHERE nama_lengkap LIKE ? ORDER BY nama_lengkap LIMIT 20",
        (f'%{q}%',),
    ).fetchall()


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

def list_periods(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        'SELECT * FROM periods ORDER BY tahun DESC, bulan DESC'
    ).fetchall()


def get_period(conn: sqlite3.Connection, period_id: int) -> sqlite3.Row | None:
    return conn.execute(
        'SELECT * FROM periods WHERE id = ?', (period_id,)
    ).fetchone()


def upsert_period(
    conn: sqlite3.Connection,
    bulan: int,
    tahun: int,
    bulan_tahun: str,
    source_file: str,
) -> int:
    existing = conn.execute(
        'SELECT id FROM periods WHERE bulan = ? AND tahun = ?', (bulan, tahun)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE periods SET source_file = ?, status = 'draft', updated_at = datetime('now') WHERE id = ?",
            (source_file, existing['id']),
        )
        conn.commit()
        return existing['id']
    cur = conn.execute(
        'INSERT INTO periods (bulan, tahun, bulan_tahun, source_file) VALUES (?, ?, ?, ?)',
        (bulan, tahun, bulan_tahun, source_file),
    )
    conn.commit()
    return cur.lastrowid


def finalize_period(conn: sqlite3.Connection, period_id: int) -> None:
    conn.execute(
        "UPDATE periods SET status = 'finalized', finalized_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (period_id,),
    )
    conn.commit()


def delete_period(conn: sqlite3.Connection, period_id: int) -> None:
    conn.execute('DELETE FROM periods WHERE id = ?', (period_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Attendance days
# ---------------------------------------------------------------------------

def upsert_attendance_day(
    conn: sqlite3.Connection,
    period_id: int,
    employee_id: int,
    row: dict[str, Any],
) -> int:
    existing = conn.execute(
        'SELECT id FROM attendance_days WHERE period_id = ? AND employee_id = ? AND tanggal = ?',
        (period_id, employee_id, row['tanggal']),
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE attendance_days SET
               pin=?, nama=?, raw_scan1=?, raw_scan2=?, raw_scan3=?,
               menit_terlambat=?, status_hari=?, catatan_otomatis=?,
               is_weekend=?, is_holiday=?, nama_libur=?, is_day1_exempt=?,
               jabatan=?, departemen=?, kantor=?, nip=?,
               adj_jam_masuk=NULL, adj_jam_keluar=NULL, catatan_manual='',
               updated_at=datetime('now')
               WHERE id=?""",
            (
                row['pin'], row['nama'], row['raw_scan1'], row['raw_scan2'], row['raw_scan3'],
                row['menit_terlambat'], row['status_hari'], row['catatan_otomatis'],
                row['is_weekend'], row['is_holiday'], row['nama_libur'], row['is_day1_exempt'],
                row.get('jabatan', ''), row.get('departemen', ''), row.get('kantor', ''), row.get('nip', ''),
                existing['id'],
            ),
        )
        return existing['id']
    cur = conn.execute(
        """INSERT INTO attendance_days
           (period_id, employee_id, pin, nama, tanggal,
            raw_scan1, raw_scan2, raw_scan3,
            menit_terlambat, status_hari, catatan_otomatis,
            is_weekend, is_holiday, nama_libur, is_day1_exempt,
            jabatan, departemen, kantor, nip)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            period_id, employee_id, row['pin'], row['nama'], row['tanggal'],
            row['raw_scan1'], row['raw_scan2'], row['raw_scan3'],
            row['menit_terlambat'], row['status_hari'], row['catatan_otomatis'],
            row['is_weekend'], row['is_holiday'], row['nama_libur'], row['is_day1_exempt'],
            row.get('jabatan', ''), row.get('departemen', ''), row.get('kantor', ''), row.get('nip', ''),
        ),
    )
    return cur.lastrowid


def get_attendance_days(
    conn: sqlite3.Connection,
    period_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        '''SELECT * FROM attendance_days
           WHERE period_id = ?
           ORDER BY pin, tanggal''',
        (period_id,),
    ).fetchall()


def get_attendance_day(conn: sqlite3.Connection, day_id: int) -> sqlite3.Row | None:
    return conn.execute(
        'SELECT * FROM attendance_days WHERE id = ?', (day_id,)
    ).fetchone()


def update_attendance_day(
    conn: sqlite3.Connection,
    day_id: int,
    fields: dict[str, Any],
) -> None:
    allowed = {
        'adj_jam_masuk', 'adj_jam_keluar', 'status_hari',
        'catatan_manual', 'menit_terlambat',
        'adj_keterlambatan', 'adj_absen',
    }
    sets = ', '.join(f'{k} = ?' for k in fields if k in allowed)
    vals = [v for k, v in fields.items() if k in allowed]
    if not sets:
        return
    vals.append(day_id)
    conn.execute(
        f"UPDATE attendance_days SET {sets}, updated_at = datetime('now') WHERE id = ?",
        vals,
    )
    conn.commit()


def get_period_employees(conn: sqlite3.Connection, period_id: int) -> list[sqlite3.Row]:
    """Returns distinct employees who have rows in a period, sorted by name."""
    return conn.execute(
        '''SELECT DISTINCT employee_id, pin, nama, jabatan, departemen, kantor, nip
           FROM attendance_days WHERE period_id = ?
           ORDER BY nama''',
        (period_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# Adjustments
# ---------------------------------------------------------------------------

def create_adjustment(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    cur = conn.execute(
        """INSERT INTO adjustments
           (period_id, attendance_day_id, employee_id, tanggal_from, tanggal_to,
            tipe, kode_alasan, catatan, author, jam_masuk_koreksi, jam_keluar_koreksi)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data['period_id'], data.get('attendance_day_id'), data.get('employee_id'),
            data['tanggal_from'], data['tanggal_to'],
            data['tipe'], data.get('kode_alasan'), data.get('catatan'),
            data.get('author', 'HR'),
            data.get('jam_masuk_koreksi'), data.get('jam_keluar_koreksi'),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_adjustments_for_period(conn: sqlite3.Connection, period_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        '''SELECT a.*,
               COALESCE(e.nama_lengkap, e2.nama_lengkap, '— (massal)') AS nama_lengkap
           FROM adjustments a
           LEFT JOIN employees e ON e.id = a.employee_id
           LEFT JOIN attendance_days ad ON ad.id = a.attendance_day_id
           LEFT JOIN employees e2 ON e2.id = ad.employee_id
           WHERE a.period_id = ?
           ORDER BY a.created_at''',
        (period_id,),
    ).fetchall()


def get_adjustments_for_day(conn: sqlite3.Connection, day_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        'SELECT * FROM adjustments WHERE attendance_day_id = ? ORDER BY created_at',
        (day_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(conn: sqlite3.Connection, key: str, default: str = '') -> str:
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        'INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (key, value),
    )
    conn.commit()


def get_all_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}
