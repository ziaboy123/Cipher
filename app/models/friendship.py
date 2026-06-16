from datetime import datetime, timezone
from app.extensions import db


class FriendRequest(db.Model):
    __tablename__ = "friend_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending")  # pending | accepted | blocked
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("requester_id", "addressee_id"),
        db.CheckConstraint("requester_id != addressee_id", name="no_self_friend"),
    )
