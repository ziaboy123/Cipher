import re
import time
from collections import deque
from flask import session, request
from flask_socketio import join_room, leave_room, emit, close_room, disconnect
from app.extensions import socketio, visitor_ip
import app.rooms as rooms

# Per-person flood limits: (max events, per seconds)
_LIMITS = {"message": (10, 10.0), "typing": (30, 10.0)}

# Every open socket.io request (a websocket, or a long poll) holds one of
# eventlet's 1024 server greenthreads, so without caps one person could tie
# them all up and Cipher would stop for everyone. A visitor (IP) gets this
# many socket.io requests open at once, counted where they're actually held...
MAX_REQUESTS_PER_VISITOR = 25
# ...this many sockets (engine.io handshakes), room or not...
MAX_SOCKETS_PER_VISITOR = 20
# ...and one person in a room gets this many (a few tabs). A new tab past
# this closes their oldest, so the one you're looking at always works.
MAX_SOCKETS_PER_SESSION = 3
# A socket that hasn't got into a room by now (no session, refused, or
# kicked) gets hung up on instead of sitting there holding a greenthread
_JOIN_GRACE = 15.0
_SWEEP_EVERY = 5.0

# Messages arrive already encrypted in the browser: iv + AES-GCM ciphertext as
# base64url. 8200 chars fits the worst case: a 1000-character message that is
# all JSON-escaped characters (6 bytes each) plus the sealed sender name.
_CIPHERTEXT_RE = re.compile(r"^[A-Za-z0-9_-]{40,8200}$")

# { (kind, sess): deque of event times }. Keyed by person, not socket, so
# extra tabs or reconnecting doesn't buy a fresh allowance. The sweeper
# clears out old entries.
_recent: dict[tuple[str, str], deque] = {}

# Engine.io sockets (one per tab, before any room) and who opened them
_eio_open: dict[str, tuple[str, float]] = {}  # eio sid -> (visitor, opened at)
_per_visitor: dict[str, int] = {}             # visitor -> open sockets
_in_flight: dict[str, int] = {}               # visitor -> socket.io requests open right now


def _allowed(kind: str) -> bool:
    limit, window = _LIMITS[kind]
    now = time.monotonic()
    q = _recent.setdefault((kind, session.get("sess", request.sid)), deque())
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _closed(eio_sid: str) -> None:
    opened = _eio_open.pop(eio_sid, None)
    if opened:
        who = opened[0]
        _per_visitor[who] -= 1
        if _per_visitor[who] <= 0:
            del _per_visitor[who]


def cap_requests(wsgi_app, path: str = "/cipher/socket.io"):
    # Wraps the whole app (socket.io included). One handshake can have any
    # number of websocket upgrades or long polls hanging off it, and under
    # eventlet each one runs inside this call until it ends, so counting here
    # counts the greenthreads a visitor is really holding.
    def capped(environ, start_response):
        if not environ.get("PATH_INFO", "").startswith(path):
            return wsgi_app(environ, start_response)
        who = visitor_ip(environ)
        if _in_flight.get(who, 0) >= MAX_REQUESTS_PER_VISITOR:
            start_response("429 Too Many Requests", [("Content-Type", "text/plain")])
            return [b"Too many connections from you. Close some tabs and try again."]
        _in_flight[who] = _in_flight.get(who, 0) + 1
        try:
            return wsgi_app(environ, start_response)
        finally:
            _in_flight[who] -= 1
            if _in_flight[who] <= 0:
                del _in_flight[who]
    return capped


def guard_engineio(eio) -> None:
    # Count sockets at the engine.io level, before Socket.IO or the session
    # get a look in, so someone with no invite can't open more than
    # MAX_SOCKETS_PER_VISITOR (cap_requests limits the requests hanging off
    # them). We wrap python-socketio's own handlers.
    sio_connect = eio.handlers["connect"]
    sio_disconnect = eio.handlers["disconnect"]
    sweeper = []

    def on_eio_connect(eio_sid, environ):
        who = visitor_ip(environ)
        if _per_visitor.get(who, 0) >= MAX_SOCKETS_PER_VISITOR:
            return False  # engine.io answers 401 and never opens the socket
        _per_visitor[who] = _per_visitor.get(who, 0) + 1
        _eio_open[eio_sid] = (who, time.monotonic())
        if not sweeper:
            sweeper.append(eio.start_background_task(_sweep_forever, eio))
        return sio_connect(eio_sid, environ)

    def on_eio_disconnect(eio_sid, *args):
        _closed(eio_sid)
        return sio_disconnect(eio_sid, *args)

    eio.on("connect", on_eio_connect)
    eio.on("disconnect", on_eio_disconnect)


def sweep(eio, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    for eio_sid, (_, opened) in list(_eio_open.items()):
        sock = eio.sockets.get(eio_sid)
        if sock is None:
            _closed(eio_sid)  # gone without a disconnect event: just forget it
        elif now - opened > _JOIN_GRACE and \
                socketio.server.manager.sid_from_eio_sid(eio_sid, "/") is None:
            # Not in a room: hang up. wait=False like engine.io's own ping
            # timeout, because waiting would hang forever on a polling client
            # that never polls again. engine.io's cleanup drops it after.
            _closed(eio_sid)
            sock.close(wait=False, abort=False)
    longest = max(window for _, window in _LIMITS.values())
    for key, q in list(_recent.items()):
        if not q or now - q[-1] > longest:
            del _recent[key]


def _sweep_forever(eio) -> None:
    while True:
        socketio.sleep(_SWEEP_EVERY)
        try:
            sweep(eio)
        except Exception:  # noqa: BLE001 - keep sweeping whatever happens
            pass


@socketio.on("connect")
def on_connect():
    code = session.get("room")
    name = session.get("name")
    sess = session.get("sess")
    tag = session.get("name_tag", "")

    if not code or not name or not sess:
        return False  # reject

    if not rooms.exists(code):
        emit("error", {"message": "This room no longer exists."})
        return False

    # Same name checks as /join, for two joins that raced past it together
    if rooms.name_taken(code, tag, except_sess=sess) or not rooms.claim_name(code, name, sess):
        emit("error", {"message": "That name is taken in this room. Choose another."})
        return False

    earlier = rooms.session_sids(code, sess)

    # name is the sealed (encrypted) display name; only the browsers can read it
    rooms.join(code, request.sid, name, tag, sess)
    join_room(code)

    # Room state only to the new joiner. No backlog: you only see what's said after you arrive.
    emit("room_state", {
        "members": rooms.member_names(code),
        "locked": rooms.is_locked(code),
    })

    # Another tab (or a refresh) of someone already here: nothing new to tell the room
    if not earlier:
        msg = rooms.make_event("joined", name)
        emit("system_message", msg, to=code, skip_sid=request.sid)
        emit("member_update", {"members": rooms.member_names(code)}, to=code)

    # Too many tabs: close the oldest ones
    for sid in earlier[:max(0, len(earlier) + 1 - MAX_SOCKETS_PER_SESSION)]:
        emit("error", {"message": "This room is open in too many tabs, so this one was closed."}, to=sid)
        disconnect(sid=sid)


@socketio.on("disconnect")
def on_disconnect():
    code = session.get("room")
    if not code or not rooms.exists(code):
        return

    name = rooms.leave(code, request.sid)
    if not name:
        return

    leave_room(code)

    # Still open in another tab, so they haven't actually left
    if rooms.session_sids(code, session.get("sess", "")):
        return

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
