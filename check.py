import os
os.environ.setdefault("CIPHER_DEV", "1")

import base64
import hashlib
import secrets
import time

from app import create_app
from app.extensions import socketio
import app.rooms as rooms

flask_app = create_app()


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def key_check_for(key: bytes) -> str:
    # Same one-way hash the browser makes in crypto.js
    return b64u(hashlib.sha256(b"cipher/v1/key-check:" + key).digest())


def sealed():
    # Stand-in for a name sealed in the browser: the server treats it as opaque
    return b64u(secrets.token_bytes(40))


def tag():
    return b64u(secrets.token_bytes(32))


KEY = secrets.token_bytes(32)
KEY_CHECK = key_check_for(KEY)
FAKE_CIPHERTEXT = b64u(secrets.token_bytes(60))
ALICE, ALICE_TAG = sealed(), tag()
BOB, BOB_TAG = sealed(), tag()

with flask_app.app_context():
    # Verify app factory + routes mount correctly
    rules = [str(r) for r in flask_app.url_map.iter_rules()]
    assert '/cipher/create' in rules, "Missing /cipher/create"
    assert '/cipher/join'   in rules, "Missing /cipher/join"
    assert '/cipher/r/<code>' in rules, "Missing /cipher/r/<code>"
    print("Routes OK:", [r for r in rules if not r.startswith('/cipher/static')])

# Verify room store
code = rooms.create(KEY_CHECK)
assert rooms.exists(code)
assert len(code) == 8
assert code.isalnum()
assert rooms.key_matches(code, KEY_CHECK)
assert not rooms.key_matches(code, key_check_for(secrets.token_bytes(32)))
assert "messages" not in rooms._store[code], "Rooms must not store messages"

rooms.join(code, "sid-1", ALICE, ALICE_TAG, "sess-a")
rooms.join(code, "sid-2", BOB, BOB_TAG, "sess-b")
rooms.join(code, "sid-3", ALICE, ALICE_TAG, "sess-a")  # Alice's second tab
assert rooms.member_count(code) == 2, "Two tabs are still one person"
assert sorted(rooms.member_names(code)) == sorted([ALICE, BOB]), "Members list each person once"
assert rooms.session_sids(code, "sess-a") == ["sid-1", "sid-3"]
assert rooms.name_taken(code, ALICE_TAG)
assert not rooms.name_taken(code, ALICE_TAG, except_sess="sess-a"), "Your own tabs don't take your name"
assert not rooms.name_taken(code, tag())

# A sealed name belongs to the join that first used it: a copy is refused
assert rooms.claim_name(code, ALICE, "sess-a") and rooms.claim_name(code, ALICE, "sess-a")
assert not rooms.claim_name(code, ALICE, "sess-b"), "A copy of someone's sealed name was let in"
for i in range(rooms._MAX_CLAIMS):
    rooms.claim_name(code, f"gone-{i}", f"sess-gone-{i}")
assert rooms.claim_name(code, sealed(), "sess-new")
assert len(rooms._store[code]["claims"]) < 10, "Claims from people who left weren't forgotten"
assert not rooms.claim_name(code, ALICE, "sess-b"), "Forgot the claim of someone still here"

name = rooms.leave(code, "sid-1")
assert name == ALICE
assert rooms.member_count(code) == 2
rooms.leave(code, "sid-3")
assert rooms.member_count(code) == 1

rooms.destroy(code)
assert not rooms.exists(code)

# People are listed in the order they joined, even after a refresh (new
# socket), so every browser numbers lookalike names the same way
code = rooms.create(KEY_CHECK)
rooms.claim_name(code, ALICE, "sess-a")
rooms.claim_name(code, BOB, "sess-b")
rooms.join(code, "sid-b", BOB, BOB_TAG, "sess-b")
rooms.join(code, "sid-a", ALICE, ALICE_TAG, "sess-a")
assert rooms.member_names(code) == [ALICE, BOB], "Members should be in join order"
rooms.leave(code, "sid-a")
rooms.join(code, "sid-a2", ALICE, ALICE_TAG, "sess-a")
assert rooms.member_names(code) == [ALICE, BOB], "A refresh moved someone down the list"
rooms.destroy(code)

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
assert 'name="name"' not in html, "A plaintext name field would be submitted to the server"
print("Headers + page OK")

# Behind the proxy, the trailing-slash redirect must stay on https
res = client.get("/cipher", headers={"X-Forwarded-Proto": "https"})
assert res.status_code == 308 and res.headers["Location"].startswith("https://"), res.headers.get("Location")
res = client.get("/cipher")
assert res.headers["Location"].startswith("http://localhost"), "Without the header, local dev stays http"
print("Proxy scheme OK")

# Only real room codes get through. A huge one used to land in the redirect's
# Location header, which was too big for nginx and took all of Cipher down.
assert client.get("/cipher/r/" + "A" * 4000).status_code == 404
assert client.get("/cipher/r/abc").status_code == 404
res = client.get("/cipher/r/abcd2345")
assert res.status_code == 302 and res.headers["Location"].endswith("code=ABCD2345")
assert "A" * 9 not in client.get("/cipher/?code=" + "A" * 4000).get_data(as_text=True)
print("Room codes OK")


def post(c, path, **form):
    with c.session_transaction() as sess:
        form["_csrf_token"] = sess["_csrf"]
    return c.post(path, data=form)


# Create needs the key check and a sealed name; join needs the right key,
# respects the lock, and refuses a duplicate name by its tag
alice = flask_app.test_client()
alice.get("/cipher/")
assert "needs JavaScript" in post(alice, "/cipher/create", name="Alice").get_data(as_text=True)
assert "needs JavaScript" in post(alice, "/cipher/create", key_check=KEY_CHECK).get_data(as_text=True)
res = post(alice, "/cipher/create", key_check=KEY_CHECK, name_sealed=ALICE, name_tag=ALICE_TAG)
assert res.status_code == 302
code = res.headers["Location"].rsplit("/", 1)[1]
with alice.session_transaction() as sess:
    assert sess["name"] == ALICE, "The session should only hold the sealed name"

bob = flask_app.test_client()
bob.get("/cipher/")
assert "full invite link" in post(bob, "/cipher/join", code=code, name_sealed=BOB, name_tag=BOB_TAG).get_data(as_text=True)
wrong = key_check_for(secrets.token_bytes(32))
assert "match this room" in post(bob, "/cipher/join", code=code, key_check=wrong, name_sealed=BOB, name_tag=BOB_TAG).get_data(as_text=True)
assert post(bob, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=BOB, name_tag=BOB_TAG).status_code == 302
print("Key-check join OK")

# Sockets: only ciphertext is relayed, nothing is stored, flood limit holds
a_sock = socketio.test_client(flask_app, flask_test_client=alice)
b_sock = socketio.test_client(flask_app, flask_test_client=bob)
assert a_sock.is_connected() and b_sock.is_connected()
state = [r for r in b_sock.get_received() if r["name"] == "room_state"][0]["args"][0]
assert "history" not in state, "Late joiners must not get a backlog"
assert sorted(state["members"]) == sorted([ALICE, BOB]), "Members should be sealed names"
joined = [r for r in a_sock.get_received() if r["name"] == "system_message"][-1]["args"][0]
assert joined["event"] == "joined" and joined["name"] == BOB and "text" not in joined

# A third person can't take a name that's already in the room (same tag)
dupe = flask_app.test_client()
dupe.get("/cipher/")
assert "name is taken" in post(dupe, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=sealed(), name_tag=BOB_TAG).get_data(as_text=True)
# ...or a copy of Bob's sealed name (everyone gets those) with a made-up tag
assert "name is taken" in post(dupe, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=BOB, name_tag=tag()).get_data(as_text=True)

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
assert sent[0]["args"][0]["name"] == ALICE, "Messages carry the sealed sender name"
print("Relay + flood limit OK")

# Lock: only the creator can, and it stops new joins
b_sock.emit("lock", {"locked": True})
assert not rooms.is_locked(code), "Non-creator locked the room"
a_sock.emit("lock", {"locked": True})
assert rooms.is_locked(code)
carol = flask_app.test_client()
carol.get("/cipher/")
assert "locked" in post(carol, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=sealed(), name_tag=tag()).get_data(as_text=True)
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

# One person can't flood a room with sockets: a new tab past the cap closes
# their oldest, the room still sees them once, and tabs share one flood limit
from app.sockets import events

alice = flask_app.test_client()
alice.get("/cipher/")
res = post(alice, "/cipher/create", key_check=KEY_CHECK, name_sealed=ALICE, name_tag=ALICE_TAG)
code = res.headers["Location"].rsplit("/", 1)[1]
bob = flask_app.test_client()
bob.get("/cipher/")
assert post(bob, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=BOB, name_tag=BOB_TAG).status_code == 302
b_sock = socketio.test_client(flask_app, flask_test_client=bob)
tabs = [socketio.test_client(flask_app, flask_test_client=alice) for _ in range(events.MAX_SOCKETS_PER_SESSION + 2)]
assert [t.is_connected() for t in tabs] == [False, False] + [True] * events.MAX_SOCKETS_PER_SESSION, "Oldest tabs should be closed"
assert "too many tabs" in [r for r in tabs[0].queue if r["name"] == "error"][-1]["args"][0]["message"]
assert rooms.member_count(code) == 2 and len(rooms._store[code]["members"]) == 1 + events.MAX_SOCKETS_PER_SESSION
seen = b_sock.get_received()
assert len([r for r in seen if r["name"] == "system_message" and r["args"][0]["event"] == "joined"]) == 1, "Extra tabs shouldn't announce a join"
assert not [r for r in seen if r["name"] == "system_message" and r["args"][0]["event"] == "left"], "A closed extra tab isn't someone leaving"
assert sorted([r for r in seen if r["name"] == "member_update"][-1]["args"][0]["members"]) == sorted([ALICE, BOB])

for i in range(6):
    tabs[-1].emit("send_message", {"content": FAKE_CIPHERTEXT})
    tabs[-2].emit("send_message", {"content": FAKE_CIPHERTEXT})
assert len([r for r in b_sock.get_received() if r["name"] == "new_message"]) == 10, "Two tabs got double the flood allowance"

# Closing every tab is leaving; closing one of several isn't
tabs[-1].disconnect()
assert not [r for r in b_sock.get_received() if r["name"] == "system_message"]
for t in tabs[-3:-1]:
    t.disconnect()
assert [r["args"][0]["event"] for r in b_sock.get_received() if r["name"] == "system_message"] == ["left"]

# A socket needs a session from /create or /join (with its join id)
stranger = flask_app.test_client()
stranger.get("/cipher/")
assert not socketio.test_client(flask_app, flask_test_client=stranger).is_connected()
with stranger.session_transaction() as sess:
    sess.update(room=code, name=sealed(), name_tag=tag())  # no join id
assert not socketio.test_client(flask_app, flask_test_client=stranger).is_connected()

# Two joins with the same name that both got past /join: only the first gets a socket
carol, carol2 = flask_app.test_client(), flask_app.test_client()
carol_tag = tag()
for c in (carol, carol2):
    c.get("/cipher/")
    assert post(c, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=sealed(), name_tag=carol_tag).status_code == 302
assert socketio.test_client(flask_app, flask_test_client=carol).is_connected()
assert not socketio.test_client(flask_app, flask_test_client=carol2).is_connected(), "Duplicate name got a socket"

# A copy of Bob's sealed name is refused even while he's between tabs (say
# mid-refresh), and he can still come back to it
b_sock.disconnect()
mal = flask_app.test_client()
mal.get("/cipher/")
assert "name is taken" in post(mal, "/cipher/join", code=code, key_check=KEY_CHECK, name_sealed=BOB, name_tag=tag()).get_data(as_text=True)
with mal.session_transaction() as sess:
    sess.update(room=code, name=BOB, name_tag=tag(), sess="sess-mallory")  # as if it raced past /join
assert not socketio.test_client(flask_app, flask_test_client=mal).is_connected(), "A copied sealed name got a socket"
b_sock = socketio.test_client(flask_app, flask_test_client=bob)
assert b_sock.is_connected(), "Bob couldn't come back to his own name"
print("Socket caps per person OK")

# Per visitor (IP), counted at the engine.io level before any session check.
# CF-Connecting-IP only counts when the request came through nginx on loopback.
eio = socketio.server.eio
eio_connect, eio_disconnect = eio.handlers["connect"], eio.handlers["disconnect"]
via_nginx = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": "203.0.113.7"}
held = [f"eio-{i}" for i in range(events.MAX_SOCKETS_PER_VISITOR)]
assert all(eio_connect(s, dict(via_nginx)) is not False for s in held)
assert eio_connect("eio-over", dict(via_nginx)) is False, "Visitor went past the socket cap"
assert eio_connect("eio-other", {**via_nginx, "HTTP_CF_CONNECTING_IP": "198.51.100.9"}) is not False, "Another visitor was blocked"
eio_disconnect(held.pop(), "client disconnect")
assert eio_connect("eio-again", dict(via_nginx)) is not False, "A closed socket didn't free its slot"
spoof = {"REMOTE_ADDR": "192.0.2.50", "HTTP_CF_CONNECTING_IP": "198.51.100.1"}
spoofed = [f"eio-spoof-{i}" for i in range(events.MAX_SOCKETS_PER_VISITOR)]
assert all(eio_connect(s, dict(spoof)) is not False for s in spoofed)
assert eio_connect("eio-spoof-over", {**spoof, "HTTP_CF_CONNECTING_IP": "198.51.100.2"}) is False, "CF-Connecting-IP trusted from a non-loopback peer"
# A whole IPv6 /64 is one visitor, or a fresh address per socket would dodge the cap
v6 = [f"eio-v6-{i}" for i in range(events.MAX_SOCKETS_PER_VISITOR)]
assert all(eio_connect(s, {**via_nginx, "HTTP_CF_CONNECTING_IP": f"2001:db8:1:2::{i + 1:x}"}) is not False
           for i, s in enumerate(v6))
assert eio_connect("eio-v6-over", {**via_nginx, "HTTP_CF_CONNECTING_IP": "2001:db8:1:2:ffff::9"}) is False, "IPv6 /64 went past the socket cap"
assert eio_connect("eio-v6-next", {**via_nginx, "HTTP_CF_CONNECTING_IP": "2001:db8:1:3::1"}) is not False, "The next /64 along was blocked"
for s in held + ["eio-again", "eio-other"] + spoofed + v6 + ["eio-v6-next"]:
    eio_disconnect(s, "client disconnect")
assert not events._per_visitor, "Socket counts leaked"


# Sockets that never get into a room are hung up on after a grace period
class FakeSocket:
    def __init__(self, eio_sid, hung_up):
        self.eio_sid, self.hung_up = eio_sid, hung_up

    def close(self, wait=True, abort=False):
        # Must not wait: a polling client that stops polling would hang it forever
        assert wait is False, "Hanging up waited on the client"
        self.hung_up.append(self.eio_sid)


class FakeEio:
    def __init__(self):
        self.sockets, self.hung_up = {}, []


fake = FakeEio()
tab = socketio.test_client(flask_app, flask_test_client=carol)  # a real one, in the room
assert tab.is_connected()
for s in ("idle", "in-room", "gone"):
    events._eio_open[s] = ("203.0.113.8", 0.0)
events._per_visitor["203.0.113.8"] = 3
fake.sockets = {s: FakeSocket(s, fake.hung_up) for s in ("idle", tab.eio_sid)}
events._eio_open[tab.eio_sid] = events._eio_open.pop("in-room")
events.sweep(fake, now=1.0)
assert fake.hung_up == [] and "gone" not in events._eio_open, "Inside the grace period only vanished sockets go"
events.sweep(fake, now=events._JOIN_GRACE + 1)
assert fake.hung_up == ["idle"], "Should hang up on the idle socket only"
assert list(events._eio_open) == [tab.eio_sid] and events._per_visitor["203.0.113.8"] == 1
events._eio_open.clear()
events._per_visitor.clear()
assert events._recent, "Flood counters from the tabs above should still be there"
events.sweep(fake, now=time.monotonic() + 60)
assert not events._recent, "Old flood counters should be cleared"
print("Socket caps per visitor OK")

# The requests hanging off those sockets (websockets, long polls) are capped
# per visitor too, counted while they're actually open
statuses = []


def call(app, environ):
    got = []
    app(environ, lambda status, headers: got.append(status))
    return got[0]


def held(environ, start_response):
    # The next request arrives while this one is still open, like a websocket parked on a sid
    if environ.get("next"):
        statuses.append(call(capped, environ["next"]))
    start_response("200 OK", [])
    return [b"ok"]


capped = events.cap_requests(held)
sio = {"PATH_INFO": "/cipher/socket.io/", **via_nginx}
chain = None
for env in reversed([sio] * events.MAX_REQUESTS_PER_VISITOR + [
        {**sio, "HTTP_CF_CONNECTING_IP": "198.51.100.3"},  # someone else
        {**sio, "PATH_INFO": "/cipher/"},                   # a page, not counted
        sio]):                                              # one too many
    chain = {**env, "next": chain}
assert call(capped, chain) == "200 OK"
assert statuses[0] == "429 Too Many Requests", "Visitor went past the request cap"
assert set(statuses[1:]) == {"200 OK"}, "Another visitor or a page got refused"
assert not events._in_flight and call(capped, dict(sio)) == "200 OK", "Finished requests didn't free their slots"


def broken(environ, start_response):
    raise RuntimeError("boom")


try:
    events.cap_requests(broken)(dict(sio), lambda *a: None)
except RuntimeError:
    pass
assert not events._in_flight, "A request that blew up kept its slot"

# And it's wired in front of the real app
events._in_flight["127.0.0.1"] = events.MAX_REQUESTS_PER_VISITOR
assert client.get("/cipher/socket.io/?EIO=4&transport=polling").status_code == 429
assert client.get("/cipher/").status_code == 200, "Pages shouldn't count"
events._in_flight.clear()
print("Request caps per visitor OK")

print("All checks passed.")
