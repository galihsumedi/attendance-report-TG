import os

from flask import (
    Blueprint, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from werkzeug.utils import secure_filename

from auth import login_required
from database import get_db
from models import get_employee, create_employee, add_alias
from services.scanner_service import get_unknown_aliases, parse_and_persist

bp = Blueprint('upload', __name__)


def _valid_ext(name: str) -> bool:
    return '.' in name and name.rsplit('.', 1)[1].lower() in ('xlsx', 'xls')


@bp.route('/')
@bp.route('/upload')
@login_required
def upload_page():
    return render_template('upload/index.html')


@bp.route('/upload/preflight', methods=['POST'])
@login_required
def preflight():
    if 'file' not in request.files:
        return render_template('upload/preflight.html', error='Tidak ada file yang diunggah.')
    f = request.files['file']
    if not f.filename or not _valid_ext(f.filename):
        return render_template('upload/preflight.html', error='Format file harus .xlsx atau .xls.')

    nama_aman = secure_filename(f.filename)
    upload_dir = current_app.config['UPLOAD_FOLDER']
    path = os.path.join(upload_dir, nama_aman)
    f.save(path)

    db = get_db()
    try:
        unknown, info = get_unknown_aliases(db, path)
    except ValueError as e:
        os.remove(path)
        return render_template('upload/preflight.html', error=str(e))

    return render_template(
        'upload/preflight.html',
        info=info,
        unknown=unknown,
        temp_file=nama_aman,
    )


@bp.route('/upload/match-names', methods=['POST'])
@login_required
def match_names():
    temp_file = request.form.get('temp_file', '')
    upload_dir = current_app.config['UPLOAD_FOLDER']
    path = os.path.join(upload_dir, temp_file)

    if not os.path.exists(path):
        flash('File sementara tidak ditemukan. Silakan unggah ulang.', 'error')
        return redirect(url_for('upload.upload_page'))

    aliases = request.form.getlist('alias[]')
    actions = request.form.getlist('action[]')    # 'existing' | 'new'
    emp_ids = request.form.getlist('employee_id[]')
    new_names = request.form.getlist('new_name[]')

    db = get_db()
    resolve_map: dict[str, int] = {}

    for i, alias in enumerate(aliases):
        action = actions[i] if i < len(actions) else 'new'
        if action == 'existing':
            emp_id = int(emp_ids[i]) if i < len(emp_ids) and emp_ids[i] else None
            if emp_id:
                try:
                    add_alias(db, emp_id, alias)
                except Exception:
                    pass
                resolve_map[alias] = emp_id
        else:
            full_name = new_names[i].strip() if i < len(new_names) else ''
            if not full_name:
                flash(f'Nama lengkap untuk alias "{alias}" tidak boleh kosong.', 'error')
                os.remove(path)
                return redirect(url_for('upload.upload_page'))
            emp_id = create_employee(db, full_name)
            try:
                add_alias(db, emp_id, alias)
            except Exception:
                pass
            resolve_map[alias] = emp_id

    try:
        result = parse_and_persist(db, path, resolve_map)
    except ValueError as e:
        flash(f'Error validasi: {e}', 'error')
        os.remove(path)
        return redirect(url_for('upload.upload_page'))
    except Exception as e:
        flash(f'Terjadi kesalahan saat memproses file: {e}', 'error')
        os.remove(path)
        return redirect(url_for('upload.upload_page'))
    finally:
        if os.path.exists(path):
            os.remove(path)

    flash(f'Scanlog {result["bulan_tahun"]} berhasil diproses ({result["jumlah_karyawan"]} karyawan).', 'success')
    return redirect(url_for('review.review_page', period_id=result['period_id']))
