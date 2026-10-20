import hashlib
import hmac
import ipaddress
import re
from flask import Blueprint, abort, current_app, jsonify, request
from app.extensions import socketio
import app.rooms as rooms

# Lets the operator end one room (say, after a report) without restarting
# Cipher and ending everyone else's. Use scripts/end_room.py on the server.
#
# Only reachable from a shell on the server itself:
# - the path isn't under /cipher, and nginx only forwards /cipher to Flask
# - Flask only listens on 127.0.0.1
# - anything that came through a proxy, or not from loopback, is refused
# - it needs a token derived from SECRET_KEY, which only the server has
# Every refusal is a plain 404, so the endpoint doesn't advertise itself.

operator_bp = Blueprint("operator", __name__)

_CODE_RE = re.compile(r"^[A-Z0-9]{8}$")
_PROXY_HEADERS = ("CF-Connecting-IP", "X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host", "X-Real-IP")


def operator_token(secret_key: str) -> str:
    return hmac.new(secret_key.encode(), b"cipher/v1/operator", hashlib.sha256).hexdigest()


def _from_server_shell() -> bool:
    try:
        peer = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return peer.is_loopback and not any(h in request.headers for h in _PROXY_HEADERS)


@operator_bp.route("/_operator/end-room", methods=["POST"])
def end_room():
    token = request.headers.get("X-Operator-Token", "")
    if not _from_server_shell() or not hmac.compare_digest(token, operator_token(current_app.config["SECRET_KEY"])):
        abort(404)

    code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
    if not _CODE_RE.match(code) or not rooms.exists(code):
        return jsonify(ended=False, error="No open room with that code."), 404

    # Same as the creator's burn: everyone in it sees the room close, nothing is kept
    rooms.destroy(code)
    socketio.emit("room_closed", {"ended": True}, to=code)
    socketio.close_room(code)
    return jsonify(ended=True, code=code)
