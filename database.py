from __future__ import annotations

import os
import sqlite3
from flask import Flask, g


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        db_path = os.environ.get('DATABASE_PATH', 'data/attendance.db')
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_lengkap TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employee_aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    alias       TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS periods (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bulan        INTEGER NOT NULL,
    tahun        INTEGER NOT NULL,
    bulan_tahun  TEXT NOT NULL,
    source_file  TEXT,
    status       TEXT NOT NULL DEFAULT 'draft',
    finalized_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(bulan, tahun)
);

CREATE TABLE IF NOT EXISTS attendance_days (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id        INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    employee_id      INTEGER NOT NULL REFERENCES employees(id),
    pin              TEXT NOT NULL,
    nama             TEXT NOT NULL,
    tanggal          TEXT NOT NULL,
    raw_scan1        TEXT,
    raw_scan2        TEXT,
    raw_scan3        TEXT,
    adj_jam_masuk    TEXT,
    adj_jam_keluar   TEXT,
    menit_terlambat  INTEGER NOT NULL DEFAULT 0,
    status_hari      TEXT NOT NULL DEFAULT '',
    catatan_otomatis TEXT NOT NULL DEFAULT '',
    catatan_manual   TEXT NOT NULL DEFAULT '',
    is_weekend       INTEGER NOT NULL DEFAULT 0,
    is_holiday       INTEGER NOT NULL DEFAULT 0,
    nama_libur       TEXT,
    is_day1_exempt   INTEGER NOT NULL DEFAULT 0,
    jabatan          TEXT NOT NULL DEFAULT '',
    departemen       TEXT NOT NULL DEFAULT '',
    kantor           TEXT NOT NULL DEFAULT '',
    nip              TEXT NOT NULL DEFAULT '',
    adj_keterlambatan TEXT NOT NULL DEFAULT '',
    adj_absen         TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(period_id, employee_id, tanggal)
);

CREATE TABLE IF NOT EXISTS adjustments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id           INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    attendance_day_id   INTEGER REFERENCES attendance_days(id) ON DELETE CASCADE,
    employee_id         INTEGER REFERENCES employees(id),
    tanggal_from        TEXT NOT NULL,
    tanggal_to          TEXT NOT NULL,
    tipe                TEXT NOT NULL,
    kode_alasan         TEXT,
    catatan             TEXT,
    author              TEXT NOT NULL DEFAULT 'HR',
    jam_masuk_koreksi   TEXT,
    jam_keluar_koreksi  TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    'jam_masuk_batas': '08:00',
    'jam_keluar_batas': '17:00',
    'grace_period_menit': '0',
    'hari_pertama_exempt': '1',
    'denda_per_menit': '',
    'sangsi_multiplier': '20',
}


def _seed_settings(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value),
        )


def migrasi_nama_karyawan(conn: sqlite3.Connection) -> None:
    count = conn.execute('SELECT COUNT(*) FROM employees').fetchone()[0]
    if count > 0:
        return
    try:
        from nama_karyawan import NAMA_LENGKAP
    except ImportError:
        return
    for alias, nama_lengkap in NAMA_LENGKAP.items():
        row = conn.execute(
            'SELECT id FROM employees WHERE nama_lengkap = ?', (nama_lengkap,)
        ).fetchone()
        if row:
            emp_id = row['id']
        else:
            cur = conn.execute(
                'INSERT INTO employees (nama_lengkap) VALUES (?)', (nama_lengkap,)
            )
            emp_id = cur.lastrowid
        conn.execute(
            'INSERT OR IGNORE INTO employee_aliases (employee_id, alias) VALUES (?, ?)',
            (emp_id, alias),
        )
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute('PRAGMA table_info(attendance_days)')}
    for col, definition in [
        ('adj_keterlambatan', "TEXT NOT NULL DEFAULT ''"),
        ('adj_absen', "TEXT NOT NULL DEFAULT ''"),
    ]:
        if col not in existing:
            conn.execute(f'ALTER TABLE attendance_days ADD COLUMN {col} {definition}')
    conn.commit()


def init_db(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    db_path = os.environ.get('DATABASE_PATH', 'data/attendance.db')
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    _seed_settings(conn)
    migrasi_nama_karyawan(conn)
    conn.commit()
    conn.close()
