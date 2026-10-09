import eventlet
eventlet.monkey_patch()

import os

from app import create_app
from app.config import DEV
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # log_output=False: no per-request access log (IPs + room codes) in journald
    socketio.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=DEV,
        log_output=False,
    )
