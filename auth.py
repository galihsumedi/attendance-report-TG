from __future__ import annotations

import os
from functools import wraps

import bcrypt
from flask import redirect, session, url_for


def check_password(plain: str) -> bool:
    stored_hash = os.environ.get('HR_PASSWORD_HASH', '')
    if not stored_hash:
        return plain == 'admin'
    try:
        return bcrypt.checkpw(plain.encode(), stored_hash.encode())
    except Exception:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated
