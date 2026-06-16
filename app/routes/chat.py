from flask import Blueprint, render_template, redirect, url_for, abort, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.extensions import db
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message
from app.models.user import User
from app.models.friendship import FriendRequest

chat_bp = Blueprint("chat", __name__)


def _get_user_conversations(user_id: int):
    memberships = (
        ConversationMember.query
        .filter_by(user_id=user_id)
        .join(Conversation)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    result = []
    for m in memberships:
        convo = m.conversation
        last = convo.last_message()
        other = None
        if convo.type == "direct":
            other_member = (
                ConversationMember.query
                .filter_by(conversation_id=convo.id)
                .filter(ConversationMember.user_id != user_id)
                .first()
            )
            if other_member:
                other = other_member.user
        result.append({"conversation": convo, "last_message": last, "other_user": other})
    return result


def _get_or_create_direct(user_a_id: int, user_b_id: int) -> Conversation:
    """Return existing direct conversation between two users, or create one."""
    existing = (
        db.session.query(Conversation)
        .join(ConversationMember, Conversation.id == ConversationMember.conversation_id)
        .filter(Conversation.type == "direct")
        .filter(ConversationMember.user_id == user_a_id)
        .filter(
            Conversation.id.in_(
                db.session.query(ConversationMember.conversation_id)
                .filter(ConversationMember.user_id == user_b_id)
            )
        )
        .first()
    )
    if existing:
        return existing

    convo = Conversation(type="direct")
    db.session.add(convo)
    db.session.flush()
    db.session.add(ConversationMember(conversation_id=convo.id, user_id=user_a_id))
    db.session.add(ConversationMember(conversation_id=convo.id, user_id=user_b_id))
    db.session.commit()
    return convo


@chat_bp.route("/")
@login_required
def index():
    conversations = _get_user_conversations(current_user.id)
    pending_requests = (
        FriendRequest.query
        .filter_by(addressee_id=current_user.id, status="pending")
        .all()
    )
    return render_template("chat/index.html", conversations=conversations, pending_requests=pending_requests)


@chat_bp.route("/c/<int:convo_id>")
@login_required
def room(convo_id: int):
    member = ConversationMember.query.filter_by(
        conversation_id=convo_id, user_id=current_user.id
    ).first_or_404()

    convo = member.conversation
    messages = (
        Message.query
        .filter_by(conversation_id=convo_id)
        .order_by(Message.created_at.asc())
        .limit(100)
        .all()
    )

    other_user = None
    if convo.type == "direct":
        other_member = (
            ConversationMember.query
            .filter_by(conversation_id=convo_id)
            .filter(ConversationMember.user_id != current_user.id)
            .first()
        )
        if other_member:
            other_user = other_member.user

    conversations = _get_user_conversations(current_user.id)
    return render_template(
        "chat/room.html",
        convo=convo,
        messages=messages,
        other_user=other_user,
        conversations=conversations,
        messages_json=[m.to_dict() for m in messages],
    )


@chat_bp.route("/dm/<username>")
@login_required
def open_dm(username: str):
    target = User.query.filter_by(username=username).first_or_404()
    if target.id == current_user.id:
        abort(400)
    convo = _get_or_create_direct(current_user.id, target.id)
    return redirect(url_for("chat.room", convo_id=convo.id))
