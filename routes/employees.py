from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from auth import login_required
from database import get_db
from models import (
    get_all_employees,
    get_employee,
    create_employee,
    update_employee,
    delete_employee,
    get_aliases_for_employee,
    add_alias,
    delete_alias,
    get_all_aliases,
    autocomplete_employees,
)

bp = Blueprint('employees', __name__)


@bp.route('/karyawan')
@login_required
def list_page():
    db = get_db()
    employees = get_all_employees(db)
    aliases = get_all_aliases(db)
    # Group aliases by employee_id
    alias_map: dict[int, list] = {}
    for a in aliases:
        alias_map.setdefault(a['employee_id'], []).append(a)
    return render_template('employees/list.html', employees=employees, alias_map=alias_map)


@bp.route('/karyawan/baru', methods=['GET', 'POST'])
@login_required
def new_form():
    if request.method == 'POST':
        nama = request.form.get('nama_lengkap', '').strip()
        alias = request.form.get('alias', '').strip()
        if not nama:
            flash('Nama lengkap tidak boleh kosong.', 'error')
            return render_template('employees/form.html', employee=None)
        try:
            emp_id = create_employee(get_db(), nama)
            if alias:
                try:
                    add_alias(get_db(), emp_id, alias)
                except Exception as e:
                    flash(f'Karyawan ditambahkan tapi alias gagal: {e}', 'warning')
            flash('Karyawan berhasil ditambahkan.', 'success')
            return redirect(url_for('employees.list_page'))
        except Exception as e:
            flash(f'Gagal menambah karyawan: {e}', 'error')
    return render_template('employees/form.html', employee=None)


@bp.route('/karyawan/<int:emp_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_form(emp_id):
    db = get_db()
    emp = get_employee(db, emp_id)
    if not emp:
        abort(404)
    if request.method == 'POST':
        nama = request.form.get('nama_lengkap', '').strip()
        if not nama:
            flash('Nama lengkap tidak boleh kosong.', 'error')
        else:
            try:
                update_employee(db, emp_id, nama)
                flash('Data karyawan diperbarui.', 'success')
                return redirect(url_for('employees.list_page'))
            except Exception as e:
                flash(f'Gagal memperbarui: {e}', 'error')
    aliases = get_aliases_for_employee(db, emp_id)
    return render_template('employees/form.html', employee=emp, aliases=aliases)


@bp.route('/karyawan/<int:emp_id>/delete', methods=['POST'])
@login_required
def delete(emp_id):
    db = get_db()
    try:
        delete_employee(db, emp_id)
        flash('Karyawan dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus: {e}', 'error')
    return redirect(url_for('employees.list_page'))


@bp.route('/karyawan/<int:emp_id>/alias', methods=['POST'])
@login_required
def add_alias_route(emp_id):
    alias = request.form.get('alias', '').strip()
    if not alias:
        flash('Alias tidak boleh kosong.', 'error')
        return redirect(url_for('employees.edit_form', emp_id=emp_id))
    try:
        add_alias(get_db(), emp_id, alias)
        flash('Alias ditambahkan.', 'success')
    except Exception as e:
        flash(f'Gagal menambah alias: {e}', 'error')
    return redirect(url_for('employees.edit_form', emp_id=emp_id))


@bp.route('/karyawan/alias/<int:alias_id>/delete', methods=['POST'])
@login_required
def delete_alias_route(alias_id):
    db = get_db()
    row = db.execute('SELECT employee_id FROM employee_aliases WHERE id = ?', (alias_id,)).fetchone()
    emp_id = row['employee_id'] if row else None
    try:
        delete_alias(db, alias_id)
        flash('Alias dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus alias: {e}', 'error')
    if emp_id:
        return redirect(url_for('employees.edit_form', emp_id=emp_id))
    return redirect(url_for('employees.list_page'))


@bp.route('/api/karyawan/autocomplete')
@login_required
def autocomplete():
    q = request.args.get('q', '')
    db = get_db()
    results = autocomplete_employees(db, q)
    return jsonify([{'id': r['id'], 'nama_lengkap': r['nama_lengkap']} for r in results])
