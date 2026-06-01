from flask import Blueprint, flash, redirect, render_template, request, url_for
from auth import login_required
from database import get_db
from models import get_all_settings, set_setting
from services.lateness_service import hitung_semua
from models import list_periods

bp = Blueprint('settings', __name__)

SETTINGS_FIELDS = [
    ('jam_masuk_batas', 'Jam Masuk Batas (HH:MM)', 'text', '08:00'),
    ('jam_keluar_batas', 'Jam Keluar Batas (HH:MM)', 'text', '17:00'),
    ('grace_period_menit', 'Grace Period (Menit)', 'number', '0'),
    ('hari_pertama_exempt', 'Hari Pertama Bulan Bebas Keterlambatan', 'checkbox', '1'),
    ('denda_per_menit', 'Denda per Menit (Rp)', 'number', ''),
    ('sangsi_multiplier', 'Multiplier Sangsi', 'number', '20'),
]


@bp.route('/pengaturan', methods=['GET'])
@login_required
def settings_page():
    db = get_db()
    settings = get_all_settings(db)
    return render_template('settings/index.html', settings=settings, fields=SETTINGS_FIELDS)


@bp.route('/pengaturan', methods=['POST'])
@login_required
def settings_save():
    db = get_db()
    for key, label, ftype, default in SETTINGS_FIELDS:
        if ftype == 'checkbox':
            value = '1' if request.form.get(key) else '0'
        else:
            value = request.form.get(key, default).strip()
        set_setting(db, key, value)

    # Recalculate lateness for all draft periods
    periods = list_periods(db)
    for p in periods:
        if p['status'] == 'draft':
            hitung_semua(db, p['id'])

    flash('Pengaturan disimpan. Keterlambatan dihitung ulang untuk semua periode draft.', 'success')
    return redirect(url_for('settings.settings_page'))
