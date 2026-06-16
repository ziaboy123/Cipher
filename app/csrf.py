import secrets
from functools import wraps
from flask import session, request, abort


def token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


def protect(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        t = session.get("_csrf")
        submitted = request.form.get("_csrf_token", "")
        if not t or not submitted or not secrets.compare_digest(t, submitted):
            abort(403)
        return f(*args, **kwargs)
    return wrapped
