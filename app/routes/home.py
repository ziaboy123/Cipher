import re
import secrets
from flask import Blueprint, render_template, request, session, redirect, url_for
from app.extensions import limiter
from app.csrf import protect
import app.rooms as rooms

home_bp = Blueprint("home", __name__)

# Everything below is made in the browser from the room key, which the server
# never sees. Names are checked (2–30 characters, letters/numbers/spaces/
# hyphens/apostrophes) in the browser, because the server can't read them.

# One-way hash of the room key (SHA-256, base64url)
_KEY_CHECK_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
# The display name sealed with the room key: iv + AES-GCM ciphertext, base64url
_SEALED_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{40,200}$")
# Keyed hash of the name's lookalike skeleton, for spotting duplicates (HMAC-SHA256, base64url)
_NAME_TAG_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")

_NEEDS_JS = "Cipher needs JavaScript turned on to encrypt your messages."


def _sealed_fields() -> tuple[str, str, str] | None:
    key_check = request.form.get("key_check", "")
    name = request.form.get("name_sealed", "")
    tag = request.form.get("name_tag", "")
    if _KEY_CHECK_RE.match(key_check) and _SEALED_NAME_RE.match(name) and _NAME_TAG_RE.match(tag):
        return key_check, name, tag
    return None


@home_bp.route("/")
def index():
    prefill_code = request.args.get("code", "").upper()
    if not rooms.valid_code(prefill_code):
        prefill_code = ""
    prefill_invited = bool(prefill_code)
    return render_template("home.html", prefill_code=prefill_code, prefill_invited=prefill_invited)


@home_bp.route("/create", methods=["POST"])
@protect
@limiter.limit("5 per hour")
def create():
    fields = _sealed_fields()
    if not fields:
        return render_template("home.html", error=_NEEDS_JS)
    key_check, name, tag = fields

    code = rooms.create(key_check)
    sess = _new_sess()
    rooms.claim_name(code, name, sess)
    _start_session(code, name, tag, sess, creator=True)
    return redirect(url_for("room.view", code=code))


@home_bp.route("/join", methods=["POST"])
@protect
@limiter.limit("20 per minute")
def join():
    code = request.form.get("code", "").strip().upper()

    if not rooms.valid_code(code):
        return render_template("home.html", error="Room codes are 8 characters.", prefill_code=code)

    fields = _sealed_fields()
    if not fields:
        return render_template("home.html", error="Paste the full invite link. The room code on its own can't unlock the channel.", prefill_code=code)
    key_check, name, tag = fields

    if not rooms.exists(code):
        return render_template("home.html", error="That room doesn't exist.", prefill_code=code)

    if not rooms.key_matches(code, key_check):
        return render_template("home.html", error="That invite link doesn't match this room.", prefill_code=code)

    if rooms.is_locked(code):
        return render_template("home.html", error="This channel is locked. No one new can join.", prefill_code=code)

    # Same name (by its tag), or a copy of someone's sealed name off the member list
    sess = _new_sess()
    if rooms.name_taken(code, tag) or not rooms.claim_name(code, name, sess):
        return render_template("home.html", error="That name is taken in this room. Choose another.", prefill_code=code)

    _start_session(code, name, tag, sess, creator=False)
    return redirect(url_for("room.view", code=code))


def _new_sess() -> str:
    # Random id for this join, so the socket code can tell your tabs apart from other people
    return secrets.token_urlsafe(12)


def _start_session(code: str, name: str, tag: str, sess: str, creator: bool) -> None:
    csrf = session.get('_csrf')
    session.clear()
    if csrf:
        session['_csrf'] = csrf
    session["room"] = code
    session["name"] = name      # sealed: the server can't read it
    session["name_tag"] = tag
    session["creator"] = creator
    session["sess"] = sess
