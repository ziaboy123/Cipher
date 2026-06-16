from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from flask_socketio import join_room, leave_room, emit
from app.extensions import db, socketio
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message
from app.models.user import User


def _assert_member(convo_id: int) -> bool:
    """Returns True if current_user is a member of the conversation."""
    return ConversationMember.query.filter_by(
        conversation_id=convo_id, user_id=current_user.id
    ).first() is not None


@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        return False  # Reject unauthenticated socket connections

    current_user.is_online = True
    current_user.touch()
    db.session.commit()

    # Notify all contacts that this user is now online
    emit("presence", {"user_id": current_user.id, "status": "online"}, broadcast=True, include_self=False)


@socketio.on("disconnect")
def on_disconnect():
    if not current_user.is_authenticated:
        return

    current_user.is_online = False
    current_user.touch()
    db.session.commit()

    emit("presence", {"user_id": current_user.id, "status": "offline"}, broadcast=True, include_self=False)


@socketio.on("join_conversation")
def on_join(data):
    if not current_user.is_authenticated:
        return
    convo_id = int(data.get("convo_id", 0))
    if not _assert_member(convo_id):
        return
    join_room(f"convo:{convo_id}")


@socketio.on("leave_conversation")
def on_leave(data):
    if not current_user.is_authenticated:
        return
    convo_id = int(data.get("convo_id", 0))
    leave_room(f"convo:{convo_id}")


@socketio.on("send_message")
def on_message(data):
    if not current_user.is_authenticated:
        return

    convo_id = int(data.get("convo_id", 0))
    content = str(data.get("content", "")).strip()

    if not content or len(content) > 2000:
        return
    if not _assert_member(convo_id):
        return

    msg = Message(
        conversation_id=convo_id,
        sender_id=current_user.id,
        content=content,
        type="text",
    )
    db.session.add(msg)

    convo = db.session.get(Conversation, convo_id)
    convo.touch()
    db.session.commit()

    emit("new_message", msg.to_dict(), to=f"convo:{convo_id}")


@socketio.on("typing")
def on_typing(data):
    if not current_user.is_authenticated:
        return
    convo_id = int(data.get("convo_id", 0))
    if not _assert_member(convo_id):
        return
    emit(
        "user_typing",
        {"user_id": current_user.id, "display_name": current_user.display_name},
        to=f"convo:{convo_id}",
        skip_sid=request.sid,
    )


@socketio.on("stop_typing")
def on_stop_typing(data):
    if not current_user.is_authenticated:
        return
    convo_id = int(data.get("convo_id", 0))
    if not _assert_member(convo_id):
        return
    emit(
        "user_stop_typing",
        {"user_id": current_user.id},
        to=f"convo:{convo_id}",
        skip_sid=request.sid,
    )


@socketio.on("mark_read")
def on_mark_read(data):
    if not current_user.is_authenticated:
        return
    convo_id = int(data.get("convo_id", 0))
    message_id = int(data.get("message_id", 0))
    member = ConversationMember.query.filter_by(
        conversation_id=convo_id, user_id=current_user.id
    ).first()
    if member:
        member.last_read_message_id = message_id
        db.session.commit()
