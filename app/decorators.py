from functools import wraps
from flask import session, redirect, url_for, request, abort

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or 'role' not in session:
            return redirect(url_for('auth.login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or 'role' not in session:
            return redirect(url_for('auth.login_page', next=request.path))
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated
