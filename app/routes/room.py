from flask import Blueprint, render_template, session, redirect, url_for, request
import app.rooms as rooms

room_bp = Blueprint("room", __name__)


@room_bp.route("/r/<code>")
def view(code: str):
    code = code.upper()

    session_room = session.get("room")
    session_name = session.get("name")

    # No valid session for this code → redirect to home with code pre-filled
    if not session_room or not session_name or session_room != code:
        return redirect(url_for("home.index", code=code))

    # Room was destroyed (server restart or everyone left before this page loaded)
    if not rooms.exists(code):
        session.clear()
        return render_template("home.html", error="That room no longer exists.", prefill_code=code)

    return render_template("room.html", code=code, name=session_name)
