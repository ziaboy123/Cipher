from flask import Blueprint, render_template, redirect, url_for, abort, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.friendship import FriendRequest

users_bp = Blueprint("users", __name__)


def _friendship_status(user_a_id: int, user_b_id: int) -> str:
    """Returns: accepted | pending_sent | pending_received | blocked | none"""
    req = FriendRequest.query.filter(
        ((FriendRequest.requester_id == user_a_id) & (FriendRequest.addressee_id == user_b_id)) |
        ((FriendRequest.requester_id == user_b_id) & (FriendRequest.addressee_id == user_a_id))
    ).first()
    if not req:
        return "none"
    if req.status == "accepted":
        return "accepted"
    if req.status == "blocked":
        return "blocked"
    if req.requester_id == user_a_id:
        return "pending_sent"
    return "pending_received"


@users_bp.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q and len(q) >= 2:
        results = (
            User.query
            .filter(
                User.username.ilike(f"%{q}%"),
                User.id != current_user.id
            )
            .limit(20)
            .all()
        )
    return render_template("users/search.html", results=results, q=q)


@users_bp.route("/u/<username>")
@login_required
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    status = _friendship_status(current_user.id, user.id)
    return render_template("users/profile.html", user=user, friendship_status=status)


@users_bp.route("/friends/request/<int:user_id>", methods=["POST"])
@login_required
def send_request(user_id: int):
    target = db.session.get(User, user_id)
    if not target or target.id == current_user.id:
        abort(400)
    existing = FriendRequest.query.filter(
        ((FriendRequest.requester_id == current_user.id) & (FriendRequest.addressee_id == user_id)) |
        ((FriendRequest.requester_id == user_id) & (FriendRequest.addressee_id == current_user.id))
    ).first()
    if not existing:
        req = FriendRequest(requester_id=current_user.id, addressee_id=user_id)
        db.session.add(req)
        db.session.commit()
    return redirect(request.referrer or url_for("users.profile", username=target.username))


@users_bp.route("/friends/accept/<int:request_id>", methods=["POST"])
@login_required
def accept_request(request_id: int):
    req = FriendRequest.query.filter_by(id=request_id, addressee_id=current_user.id, status="pending").first_or_404()
    req.status = "accepted"
    db.session.commit()
    return redirect(request.referrer or url_for("chat.index"))


@users_bp.route("/friends/decline/<int:request_id>", methods=["POST"])
@login_required
def decline_request(request_id: int):
    req = FriendRequest.query.filter_by(id=request_id, addressee_id=current_user.id, status="pending").first_or_404()
    db.session.delete(req)
    db.session.commit()
    return redirect(request.referrer or url_for("chat.index"))


@users_bp.route("/settings")
@login_required
def settings():
    return render_template("users/settings.html")
