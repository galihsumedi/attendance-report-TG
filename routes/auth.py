from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from auth import check_password

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login_page():
    if session.get('logged_in'):
        return redirect(url_for('upload.upload_page'))
    return render_template('login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    password = request.form.get('password', '')
    if check_password(password):
        session['logged_in'] = True
        return redirect(url_for('upload.upload_page'))
    flash('Password salah.', 'error')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))
