import re
from flask import Blueprint, render_template, request, session, redirect, url_for
from app.extensions import limiter
from app.csrf import protect
import app.rooms as rooms

home_bp = Blueprint("home", __name__)

_NAME_RE = re.compile(r"^[\w '\-]+$")


def _validate_name(raw: str) -> tuple[str, str | None]:
    name = raw.strip()
    if not name:
        return name, "Enter a name to continue."
    if len(name) < 2 or len(name) > 30:
        return name, "Name must be between 2 and 30 characters."
    if not _NAME_RE.match(name):
        return name, "Letters, numbers, spaces, hyphens, and apostrophes only."
    return name, None


@home_bp.route("/")
def index():
    prefill_code = request.args.get("code", "").upper()
    prefill_invited = bool(prefill_code)
    return render_template("home.html", prefill_code=prefill_code, prefill_invited=prefill_invited)


@home_bp.route("/create", methods=["POST"])
@protect
@limiter.limit("5 per hour")
def create():
    name, err = _validate_name(request.form.get("name", ""))
    if err:
        return render_template("home.html", error=err, prefill_name=name)

    code = rooms.create(name)
    csrf = session.get('_csrf')
    session.clear()
    if csrf:
        session['_csrf'] = csrf
    session["room"] = code
    session["name"] = name
    return redirect(url_for("room.view", code=code))


@home_bp.route("/join", methods=["POST"])
@protect
@limiter.limit("20 per minute")
def join():
    name, err = _validate_name(request.form.get("name", ""))
    code = request.form.get("code", "").strip().upper()

    if err:
        return render_template("home.html", error=err, prefill_name=name, prefill_code=code)

    if not code or len(code) != 8 or not code.isalnum():
        return render_template("home.html", error="Room codes are 8 characters.", prefill_name=name, prefill_code=code)

    if not rooms.exists(code):
        return render_template("home.html", error="That room doesn't exist.", prefill_name=name, prefill_code=code)

    if rooms.name_taken(code, name):
        return render_template("home.html", error="That name is taken in this room. Choose another.", prefill_name=name, prefill_code=code)

    csrf = session.get('_csrf')
    session.clear()
    if csrf:
        session['_csrf'] = csrf
    session["room"] = code
    session["name"] = name
    return redirect(url_for("room.view", code=code))
