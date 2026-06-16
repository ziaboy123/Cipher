from flask import session, request
from flask_socketio import join_room, leave_room, emit
from app.extensions import socketio
import app.rooms as rooms


@socketio.on("connect")
def on_connect():
    code = session.get("room")
    name = session.get("name")

    if not code or not name:
        return False  # reject

    if not rooms.exists(code):
        emit("error", {"message": "This room no longer exists."})
        return False

    rooms.join(code, request.sid, name)
    join_room(code)

    # Send full room state only to the new joiner
    emit("room_state", {
        "members": rooms.member_names(code),
        "history": rooms.history(code),
    })

    # System message + member update to everyone else
    msg = rooms.make_system(f"{name} joined.")
    rooms.push(code, msg)
    emit("system_message", msg, to=code, skip_sid=request.sid)
    emit("member_update", {"members": rooms.member_names(code)}, to=code)


@socketio.on("disconnect")
def on_disconnect():
    code = session.get("room")
    if not code or not rooms.exists(code):
        return

    name = rooms.leave(code, request.sid)
    if not name:
        return

    leave_room(code)

    if rooms.member_count(code) == 0:
        rooms.destroy(code)
        # Broadcast to any lingering sockets in the room
        emit("room_closed", {}, to=code)
    else:
        msg = rooms.make_system(f"{name} left.")
        rooms.push(code, msg)
        emit("system_message", msg, to=code)
        emit("member_update", {"members": rooms.member_names(code)}, to=code)


@socketio.on("send_message")
def on_message(data):
    code = session.get("room")
    name = session.get("name")

    if not code or not name or not rooms.exists(code):
        return

    content = str(data.get("content", "")).strip()
    if not content or len(content) > 1000:
        return

    msg = rooms.make_msg(name, content)
    rooms.push(code, msg)
    emit("new_message", msg, to=code)


@socketio.on("typing")
def on_typing():
    code = session.get("room")
    name = session.get("name")
    if not code or not name or not rooms.exists(code):
        return
    emit("user_typing", {"name": name}, to=code, skip_sid=request.sid)


@socketio.on("stop_typing")
def on_stop_typing():
    code = session.get("room")
    name = session.get("name")
    if not code or not name:
        return
    emit("user_stop_typing", {"name": name}, to=code, skip_sid=request.sid)
