from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import db, bcrypt, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    bio = db.Column(db.String(200), nullable=True)

    # Used to generate deterministic avatar colours from initials
    avatar_seed = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_online = db.Column(db.Boolean, default=False)

    # Relationships
    sent_requests = db.relationship(
        "FriendRequest", foreign_keys="FriendRequest.requester_id", backref="requester", lazy="dynamic"
    )
    received_requests = db.relationship(
        "FriendRequest", foreign_keys="FriendRequest.addressee_id", backref="addressee", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def initials(self) -> str:
        parts = self.display_name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.display_name[:2].upper()

    def touch(self) -> None:
        self.last_seen = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
