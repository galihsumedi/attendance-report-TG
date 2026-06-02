from __future__ import annotations

import sqlite3
from calendar import monthrange
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth import login_required
from database import get_db
from models import (
    get_attendance_day,
    get_attendance_days,
    get_period,
    get_period_employees,
    update_attendance_day,
    create_adjustment,
    get_adjustments_for_day,
    get_all_employees,
)
from services.lateness_service import hitung_ulang

bp = Blueprint('review', __name__)

# Status values set at import time — read-only in UI
IMPORT_STATUS_VALUES = {'Tidak Ada Scan', 'Hanya Scan Masuk', '3 Scan Terdeteksi'}

# Penyesuaian Keterlambatan options — zero lateness (except koreksi_scan)
KETERLAMBATAN_CHOICES = [
    ('cuaca', 'Cuaca'),
    ('dinas_lapangan', 'Dinas Lapangan atau Kerja'),
    ('keterlambatan_disetujui', 'Keterlambatan Disetujui'),
    ('koreksi_scan', 'Koreksi Scan'),
]

# Penyesuaian Absen options — exempt from HK Tidak Ada Scan
ABSEN_CHOICES = [
    ('cuti', 'Cuti'),
    ('dinas_lapangan', 'Dinas Lapangan atau Kerja'),
    ('izin', 'Izin'),
    ('sakit', 'Sakit'),
    ('koreksi_scan', 'Koreksi Scan'),
]

# Penyesuaian Massal options
MASSAL_CHOICES = [
    ('cuaca_banjir', 'Cuaca atau Banjir'),
    ('cuti_bersama', 'Cuti Bersama'),
    ('hari_libur', 'Hari Libur'),
]


def _build_grid(conn: sqlite3.Connection, period_id: int):
    period = get_period(conn, period_id)
    if not period:
        abort(404)

    employees = get_period_employees(conn, period_id)
    days_rows = get_attendance_days(conn, period_id)

    # Index days by (pin, tanggal)
    day_index: dict[tuple, sqlite3.Row] = {}
    for d in days_rows:
        day_index[(d['pin'], d['tanggal'])] = d

    bulan = period['bulan']
    tahun = period['tahun']
    jumlah_hari = monthrange(tahun, bulan)[1]
    all_dates = [datetime(tahun, bulan, d) for d in range(1, jumlah_hari + 1)]

    grid = []
    for emp in employees:
        pin = emp['pin']
        row_days = []
        total_menit = 0
        noscan_count = 0
        for tgl in all_dates:
            tgl_str = tgl.strftime('%Y-%m-%d')
            d = day_index.get((pin, tgl_str))
            row_days.append(d)
            if d:
                total_menit += d['menit_terlambat']
                is_workday = not d['is_weekend'] and not d['is_holiday']
                has_scan = d['adj_jam_masuk'] or d['raw_scan1']
                absen_exempt = bool(d['adj_absen'])
                if is_workday and not has_scan and not absen_exempt:
                    noscan_count += 1
        grid.append({
            'emp': emp,
            'days': row_days,
            'total_menit': total_menit,
            'noscan_count': noscan_count,
        })

    return period, all_dates, grid


@bp.route('/periode/<int:period_id>/review')
@login_required
def review_page(period_id):
    db = get_db()
    period, all_dates, grid = _build_grid(db, period_id)
    employees = get_all_employees(db)
    return render_template(
        'review/index.html',
        period=period,
        all_dates=all_dates,
        grid=grid,
        keterlambatan_choices=KETERLAMBATAN_CHOICES,
        absen_choices=ABSEN_CHOICES,
        massal_choices=MASSAL_CHOICES,
        employees=employees,
    )


@bp.route('/periode/<int:period_id>/review/grid')
@login_required
def grid_partial(period_id):
    db = get_db()
    period, all_dates, grid = _build_grid(db, period_id)
    return render_template(
        'review/_grid.html',
        period=period,
        all_dates=all_dates,
        grid=grid,
        keterlambatan_choices=KETERLAMBATAN_CHOICES,
        absen_choices=ABSEN_CHOICES,
        massal_choices=MASSAL_CHOICES,
    )


@bp.route('/periode/<int:period_id>/review/cell/<int:day_id>')
@login_required
def cell_view(period_id, day_id):
    db = get_db()
    day = get_attendance_day(db, day_id)
    if not day or day['period_id'] != period_id:
        abort(404)
    adj_history = get_adjustments_for_day(db, day_id)
    return render_template('review/_cell.html', day=day, adj_history=adj_history, period_id=period_id)


@bp.route('/periode/<int:period_id>/review/cell/<int:day_id>/edit')
@login_required
def cell_edit_form(period_id, day_id):
    db = get_db()
    day = get_attendance_day(db, day_id)
    if not day or day['period_id'] != period_id:
        abort(404)
    return render_template(
        'review/_cell_edit.html',
        day=day,
        period_id=period_id,
        keterlambatan_choices=KETERLAMBATAN_CHOICES,
        absen_choices=ABSEN_CHOICES,
    )


@bp.route('/periode/<int:period_id>/review/cell/<int:day_id>/save', methods=['POST'])
@login_required
def cell_save(period_id, day_id):
    db = get_db()
    day = get_attendance_day(db, day_id)
    if not day or day['period_id'] != period_id:
        abort(404)

    adj_jam_masuk = request.form.get('adj_jam_masuk', '').strip() or None
    adj_jam_keluar = request.form.get('adj_jam_keluar', '').strip() or None
    catatan_manual = request.form.get('catatan_manual', '').strip()
    adj_keterlambatan = request.form.get('adj_keterlambatan', '').strip()
    adj_absen = request.form.get('adj_absen', '').strip()

    update_attendance_day(db, day_id, {
        'adj_jam_masuk': adj_jam_masuk,
        'adj_jam_keluar': adj_jam_keluar,
        'catatan_manual': catatan_manual,
        'adj_keterlambatan': adj_keterlambatan,
        'adj_absen': adj_absen,
    })

    # Log to adjustments audit table
    for tipe_val in [adj_keterlambatan, adj_absen]:
        if tipe_val:
            create_adjustment(db, {
                'period_id': period_id,
                'attendance_day_id': day_id,
                'employee_id': day['employee_id'],
                'tanggal_from': day['tanggal'],
                'tanggal_to': day['tanggal'],
                'tipe': tipe_val,
                'catatan': catatan_manual,
            })

    hitung_ulang(db, day_id)

    day = get_attendance_day(db, day_id)
    adj_history = get_adjustments_for_day(db, day_id)

    # Build OOB totals for the employee row
    all_days = db.execute(
        'SELECT menit_terlambat, is_weekend, is_holiday, raw_scan1, adj_jam_masuk, adj_absen FROM attendance_days WHERE period_id = ? AND pin = ?',
        (period_id, day['pin']),
    ).fetchall()
    total_menit = sum(r['menit_terlambat'] for r in all_days)
    noscan_count = sum(
        1 for r in all_days
        if not r['is_weekend'] and not r['is_holiday']
        and not (r['adj_jam_masuk'] or r['raw_scan1'])
        and not r['adj_absen']
    )

    return render_template(
        'review/_cell.html',
        day=day,
        adj_history=adj_history,
        period_id=period_id,
        oob_pin=day['pin'],
        oob_total=total_menit,
        oob_noscan=noscan_count,
    )


@bp.route('/periode/<int:period_id>/review/bulk', methods=['POST'])
@login_required
def bulk_adjust(period_id):
    db = get_db()
    period = get_period(db, period_id)
    if not period:
        abort(404)

    tipe_massal = request.form.get('tipe', '').strip()
    tanggal = request.form.get('tanggal', '').strip()
    catatan = request.form.get('catatan', '').strip()

    if tipe_massal not in ('cuaca_banjir', 'cuti_bersama', 'hari_libur') or not tanggal:
        flash('Tipe dan tanggal harus diisi.', 'error')
        return redirect(url_for('review.review_page', period_id=period_id))

    affected = db.execute(
        'SELECT id FROM attendance_days WHERE period_id = ? AND tanggal = ? AND is_weekend = 0 AND is_holiday = 0',
        (period_id, tanggal),
    ).fetchall()

    # cuaca_banjir → zero lateness + exempt noscan
    # cuti_bersama → zero lateness + exempt noscan
    # Both affect both dimensions
    for row in affected:
        update_attendance_day(db, row['id'], {
            'adj_keterlambatan': tipe_massal,
            'adj_absen': tipe_massal,
            'catatan_manual': catatan,
        })
        hitung_ulang(db, row['id'])

    # One audit record for the entire bulk action
    if affected:
        create_adjustment(db, {
            'period_id': period_id,
            'attendance_day_id': None,
            'employee_id': None,
            'tanggal_from': tanggal,
            'tanggal_to': tanggal,
            'tipe': tipe_massal,
            'catatan': f'[Massal] {catatan} ({len(affected)} karyawan)',
        })

    label = dict(MASSAL_CHOICES).get(tipe_massal, tipe_massal)
    flash(f'Penyesuaian massal "{label}" diterapkan ke {len(affected)} karyawan.', 'success')
    return redirect(url_for('review.review_page', period_id=period_id))
