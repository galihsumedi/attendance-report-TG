from flask import Blueprint, flash, redirect, render_template, url_for
from auth import login_required
from database import get_db
from models import list_periods, delete_period, get_period

bp = Blueprint('periods', __name__)


@bp.route('/periode')
@login_required
def list_page():
    db = get_db()
    periods = list_periods(db)
    return render_template('periods/list.html', periods=periods)


@bp.route('/periode/<int:period_id>/delete', methods=['POST'])
@login_required
def delete(period_id):
    db = get_db()
    p = get_period(db, period_id)
    if p and p['status'] == 'draft':
        delete_period(db, period_id)
        flash('Periode dihapus.', 'success')
    else:
        flash('Hanya periode draft yang dapat dihapus.', 'error')
    return redirect(url_for('periods.list_page'))
