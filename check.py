import os
os.environ.setdefault("CIPHER_DEV", "1")

import base64
import hashlib
import secrets

from app import create_app
from app.extensions import socketio
import app.rooms as rooms

flask_app = create_app()


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def key_check_for(key: bytes) -> str:
    # Same one-way hash the browser makes in crypto.js
    return b64u(hashlib.sha256(b"cipher/v1/key-check:" + key).digest())


KEY = secrets.token_bytes(32)
KEY_CHECK = key_check_for(KEY)
FAKE_CIPHERTEXT = b64u(secrets.token_bytes(60))

with flask_app.app_context():
    # Verify app factory + routes mount correctly
    rules = [str(r) for r in flask_app.url_map.iter_rules()]
    assert '/cipher/create' in rules, "Missing /cipher/create"
    assert '/cipher/join'   in rules, "Missing /cipher/join"
    assert '/cipher/r/<code>' in rules, "Missing /cipher/r/<code>"
    print("Routes OK:", [r for r in rules if not r.startswith('/cipher/static')])

# Verify room store
code = rooms.create("Alice", KEY_CHECK)
assert rooms.exists(code)
assert len(code) == 8
assert code.isalnum()
assert rooms.key_matches(code, KEY_CHECK)
assert not rooms.key_matches(code, key_check_for(secrets.token_bytes(32)))
assert "messages" not in rooms._store[code], "Rooms must not store messages"

rooms.join(code, "sid-1", "Alice")
rooms.join(code, "sid-2", "Bob")
assert rooms.member_count(code) == 2
assert rooms.name_taken(code, "alice")
assert not rooms.name_taken(code, "Carol")
assert rooms.member_names(code) == ["Alice", "Bob"]

name = rooms.leave(code, "sid-1")
assert name == "Alice"
assert rooms.member_count(code) == 1

rooms.destroy(code)
assert not rooms.exists(code)

print("Room store OK")

# Security headers, and no inline scripts/styles or third-party URLs in pages
client = flask_app.test_client()
res = client.get("/cipher/")
assert res.status_code == 200
assert "script-src 'self'" in res.headers["Content-Security-Policy"]
assert res.headers["Cache-Control"] == "no-store"
html = res.get_data(as_text=True)
assert "<script>" not in html and "style=" not in html, "Inline code is blocked by the CSP"
assert "googleapis" not in html and "cdn." not in html, "Third-party asset in page"
assert "?v=" in html, "Asset URLs aren't versioned"
print("Headers + page OK")


def post(c, path, **form):
    with c.session_transaction() as sess:
        form["_csrf_token"] = sess["_csrf"]
    return c.post(path, data=form)


# Create needs the key check; join needs the right one, and respects the lock
alice = flask_app.test_client()
alice.get("/cipher/")
assert "needs JavaScript" in post(alice, "/cipher/create", name="Alice").get_data(as_text=True)
res = post(alice, "/cipher/create", name="Alice", key_check=KEY_CHECK)
assert res.status_code == 302
code = res.headers["Location"].rsplit("/", 1)[1]

bob = flask_app.test_client()
bob.get("/cipher/")
assert "full invite link" in post(bob, "/cipher/join", name="Bob", code=code).get_data(as_text=True)
wrong = key_check_for(secrets.token_bytes(32))
assert "match this room" in post(bob, "/cipher/join", name="Bob", code=code, key_check=wrong).get_data(as_text=True)
assert post(bob, "/cipher/join", name="Bob", code=code, key_check=KEY_CHECK).status_code == 302
print("Key-check join OK")

# Sockets: only ciphertext is relayed, nothing is stored, flood limit holds
a_sock = socketio.test_client(flask_app, flask_test_client=alice)
b_sock = socketio.test_client(flask_app, flask_test_client=bob)
assert a_sock.is_connected() and b_sock.is_connected()
state = [r for r in b_sock.get_received() if r["name"] == "room_state"][0]["args"][0]
assert "history" not in state, "Late joiners must not get a backlog"
a_sock.get_received()

a_sock.emit("send_message", {"content": "plain text is refused"})
a_sock.emit("send_message", "not a dict")
assert not [r for r in b_sock.get_received() if r["name"] == "new_message"], "Plaintext was relayed"

for i in range(12):
    a_sock.emit("send_message", {"content": FAKE_CIPHERTEXT})
received = a_sock.get_received()
sent = [r for r in received if r["name"] == "new_message"]
errors = [r for r in received if r["name"] == "error"]
assert len(sent) == 10, f"expected 10 delivered, got {len(sent)}"
assert len(errors) == 2, f"expected 2 slow-down errors, got {len(errors)}"
assert sent[0]["args"][0]["content"] == FAKE_CIPHERTEXT
print("Relay + flood limit OK")

# Lock: only the creator can, and it stops new joins
b_sock.emit("lock", {"locked": True})
assert not rooms.is_locked(code), "Non-creator locked the room"
a_sock.emit("lock", {"locked": True})
assert rooms.is_locked(code)
carol = flask_app.test_client()
carol.get("/cipher/")
assert "locked" in post(carol, "/cipher/join", name="Carol", code=code, key_check=KEY_CHECK).get_data(as_text=True)
a_sock.emit("lock", {"locked": False})
assert not rooms.is_locked(code)
print("Lock OK")

# Burn: only the creator can, and it ends the room for everyone
b_sock.get_received()
b_sock.emit("burn")
assert rooms.exists(code), "Non-creator burned the room"
a_sock.emit("burn")
assert not rooms.exists(code)
closed = [r for r in b_sock.get_received() if r["name"] == "room_closed"]
assert closed and closed[0]["args"][0] == {"burned": True}
a_sock.disconnect()
b_sock.disconnect()
print("Burn OK")

print("All checks passed.")
