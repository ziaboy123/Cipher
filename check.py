from app import create_app
import app.rooms as rooms

flask_app = create_app()

with flask_app.app_context():
    # Verify app factory + routes mount correctly
    rules = [str(r) for r in flask_app.url_map.iter_rules()]
    assert '/create' in rules, "Missing /create"
    assert '/join'   in rules, "Missing /join"
    assert '/r/<code>' in rules, "Missing /r/<code>"
    print("Routes OK:", [r for r in rules if r not in ('/static/<path:filename>',)])

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
print("All checks passed.")
