from datetime import datetime, timezone
from app.extensions import db


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # None for system messages
    content = db.Column(db.String(2000), nullable=False)
    type = db.Column(db.String(10), nullable=False, default="text")  # text | system

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_username": self.sender.username if self.sender else None,
            "sender_display_name": self.sender.display_name if self.sender else None,
            "sender_initials": self.sender.initials() if self.sender else None,
            "content": self.content if not self.deleted_at else None,
            "type": self.type,
            "created_at": self.created_at.isoformat(),
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "is_deleted": self.deleted_at is not None,
        }
