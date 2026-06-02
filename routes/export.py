import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, send_file, url_for

from auth import login_required
from database import get_db
from models import get_period, finalize_period
from services.export_service import buat_excel_dari_db

bp = Blueprint('export', __name__)


@bp.route('/periode/<int:period_id>/finalize', methods=['POST'])
@login_required
def finalize(period_id):
    db = get_db()
    p = get_period(db, period_id)
    if not p:
        abort(404)
    if p['status'] != 'finalized':
        finalize_period(db, period_id)
        flash(f'Periode {p["bulan_tahun"]} telah difinalisasi.', 'success')
    return redirect(url_for('review.review_page', period_id=period_id))


@bp.route('/periode/<int:period_id>/export')
@login_required
def download_excel(period_id):
    db = get_db()
    p = get_period(db, period_id)
    if not p:
        abort(404)

    output_dir = current_app.config['OUTPUT_FOLDER']
    os.makedirs(output_dir, exist_ok=True)
    nama_file = f"Laporan_Kehadiran_{p['bulan_tahun'].replace(' ', '_')}.xlsx"
    path_output = os.path.join(output_dir, nama_file)

    try:
        buat_excel_dari_db(db, period_id, path_output)
    except Exception as e:
        flash(f'Gagal membuat laporan: {e}', 'error')
        return redirect(url_for('review.review_page', period_id=period_id))

    return send_file(
        path_output,
        as_attachment=True,
        download_name=nama_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
