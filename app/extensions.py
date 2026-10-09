from flask import request
from flask_socketio import SocketIO
from flask_limiter import Limiter


def client_ip() -> str:
    # In production every request reaches Flask from nginx on 127.0.0.1, so
    # remote_addr alone would put the whole internet in one rate-limit bucket.
    # Cloudflare's tunnel sets CF-Connecting-IP to the real visitor's address.
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"


socketio = SocketIO()

limiter = Limiter(
    key_func=client_ip,
    default_limits=[],
    storage_uri="memory://",
)
