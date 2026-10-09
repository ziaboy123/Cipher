import os
os.environ.setdefault("CIPHER_DEV", "1")

from app import create_app
from app.extensions import socketio
import app.rooms as rooms

flask_app = create_app()

with flask_app.app_context():
    # Verify app factory + routes mount correctly
    rules = [str(r) for r in flask_app.url_map.iter_rules()]
    assert '/cipher/create' in rules, "Missing /cipher/create"
    assert '/cipher/join'   in rules, "Missing /cipher/join"
    assert '/cipher/r/<code>' in rules, "Missing /cipher/r/<code>"
    print("Routes OK:", [r for r in rules if not r.startswith('/cipher/static')])

# Verify room store
code = rooms.create("Alice")
assert rooms.exists(code)
assert len(code) == 8
assert code.isalnum()

rooms.join(code, "sid-1", "Alice")
rooms.join(code, "sid-2", "Bob")
assert rooms.member_count(code) == 2
assert rooms.name_taken(code, "alice")
assert not rooms.name_taken(code, "Carol")
assert rooms.member_names(code) == ["Alice", "Bob"]

msg = rooms.make_msg("Alice", "hello")
rooms.push(code, msg)
assert len(rooms.history(code)) == 1

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

# Flood limit: 10 messages per 10 seconds per connection
code = rooms.create("Alice")
with client.session_transaction() as sess:
    sess["room"] = code
    sess["name"] = "Alice"
sock = socketio.test_client(flask_app, flask_test_client=client)
assert sock.is_connected()
sock.get_received()
for i in range(12):
    sock.emit("send_message", {"content": f"msg {i}"})
received = sock.get_received()
sent = [r for r in received if r["name"] == "new_message"]
errors = [r for r in received if r["name"] == "error"]
assert len(sent) == 10, f"expected 10 delivered, got {len(sent)}"
assert len(errors) == 2, f"expected 2 slow-down errors, got {len(errors)}"
sock.emit("send_message", "not a dict")  # must be ignored, not crash
sock.disconnect()
assert not rooms.exists(code), "Room should be destroyed when the last person leaves"
print("Flood limit OK")

print("All checks passed.")
