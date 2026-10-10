import re
import time
from collections import deque
from flask import session, request
from flask_socketio import join_room, leave_room, emit, close_room
from app.extensions import socketio
import app.rooms as rooms

# Per-connection flood limits: (max events, per seconds)
_LIMITS = {"message": (10, 10.0), "typing": (30, 10.0)}

# Messages arrive already encrypted in the browser: iv + AES-GCM ciphertext as
# base64url. 8200 chars fits the worst case: a 1000-character message that is
# all JSON-escaped characters (6 bytes each) plus the sealed sender name.
_CIPHERTEXT_RE = re.compile(r"^[A-Za-z0-9_-]{40,8200}$")

# { (kind, sid): deque of event times }
_recent: dict[tuple[str, str], deque] = {}


def _allowed(kind: str) -> bool:
    limit, window = _LIMITS[kind]
    now = time.monotonic()
    q = _recent.setdefault((kind, request.sid), deque())
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _forget(sid: str) -> None:
    for kind in _LIMITS:
        _recent.pop((kind, sid), None)


@socketio.on("connect")
def on_connect():
    code = session.get("room")
    name = session.get("name")

    if not code or not name:
        return False  # reject

    if not rooms.exists(code):
        emit("error", {"message": "This room no longer exists."})
        return False

    # name is the sealed (encrypted) display name; only the browsers can read it
    rooms.join(code, request.sid, name, session.get("name_tag", ""))
    join_room(code)

    # Room state only to the new joiner. No backlog: you only see what's said after you arrive.
    emit("room_state", {
        "members": rooms.member_names(code),
        "locked": rooms.is_locked(code),
    })

    # System message + member update to everyone else
    msg = rooms.make_event("joined", name)
    emit("system_message", msg, to=code, skip_sid=request.sid)
    emit("member_update", {"members": rooms.member_names(code)}, to=code)


@socketio.on("disconnect")
def on_disconnect():
    _forget(request.sid)
    code = session.get("room")
    if not code or not rooms.exists(code):
        return

    name = rooms.leave(code, request.sid)
    if not name:
        return

    leave_room(code)

    # Clear their typing indicator in case the tab crashed mid-sentence
    emit("user_stop_typing", {"name": name}, to=code)

    if rooms.member_count(code) == 0:
        rooms.destroy(code)
        # Broadcast to any lingering sockets in the room
        emit("room_closed", {}, to=code)
    else:
        msg = rooms.make_event("left", name)
        emit("system_message", msg, to=code)
        emit("member_update", {"members": rooms.member_names(code)}, to=code)


@socketio.on("send_message")
def on_message(data):
    code = session.get("room")
    name = session.get("name")

    if not code or not name or not rooms.exists(code) or not isinstance(data, dict):
        return

    content = data.get("content")
    if not isinstance(content, str) or not _CIPHERTEXT_RE.match(content):
        return

    if not _allowed("message"):
        emit("error", {"message": "You're sending messages too fast. Wait a few seconds."})
        return

    emit("new_message", rooms.make_msg(name, content), to=code)


@socketio.on("typing")
def on_typing():
    code = session.get("room")
    name = session.get("name")
    if not code or not name or not rooms.exists(code) or not _allowed("typing"):
        return
    emit("user_typing", {"name": name}, to=code, skip_sid=request.sid)


@socketio.on("stop_typing")
def on_stop_typing():
    code = session.get("room")
    name = session.get("name")
    if not code or not name or not _allowed("typing"):
        return
    emit("user_stop_typing", {"name": name}, to=code, skip_sid=request.sid)


@socketio.on("lock")
def on_lock(data):
    code = session.get("room")
    if not session.get("creator") or not code or not rooms.exists(code) or not isinstance(data, dict):
        return
    locked = bool(data.get("locked"))
    rooms.set_locked(code, locked)
    emit("system_message", rooms.make_event("locked" if locked else "unlocked"), to=code)
    emit("lock_state", {"locked": locked}, to=code)


@socketio.on("burn")
def on_burn():
    code = session.get("room")
    if not session.get("creator") or not code or not rooms.exists(code):
        return
    rooms.destroy(code)
    emit("room_closed", {"burned": True}, to=code)
    close_room(code)
