from datetime import datetime, timezone
from app.extensions import db


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False, default="direct")  # direct | group
    name = db.Column(db.String(100), nullable=True)  # only used for group convos
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    members = db.relationship("ConversationMember", backref="conversation", lazy="dynamic", cascade="all, delete-orphan")
    messages = db.relationship("Message", backref="conversation", lazy="dynamic", cascade="all, delete-orphan")

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def last_message(self):
        return self.messages.filter_by(deleted_at=None).order_by(db.text("id desc")).first()


class ConversationMember(db.Model):
    __tablename__ = "conversation_members"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_read_message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=True)

    user = db.relationship("User")

    __table_args__ = (db.UniqueConstraint("conversation_id", "user_id"),)
