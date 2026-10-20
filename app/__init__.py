import hashlib
from urllib.parse import quote
from functools import cache
from pathlib import Path
from flask import Flask, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config
from app.extensions import socketio, limiter
from app import csrf as _csrf

# Everything (scripts, styles, fonts, the socket) comes from this origin only,
# so no third party learns who visits and injected markup can't run code.
CSP = "; ".join([
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    "img-src 'self'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


# Reporting and the site-wide terms/privacy live on daniyalzia.co.uk (they cover
# every project), so Cipher links there rather than keeping its own copies.
TERMS_URL = "https://daniyalzia.co.uk/terms"
PRIVACY_URL = "https://daniyalzia.co.uk/privacy"
REPORTING_URL = "https://daniyalzia.co.uk/terms#reporting"
REPORT_EMAIL = "mail@daniyalzia.co.uk"


def report_mailto(code: str = "") -> str:
    # Nobody can read Cipher's messages, so the report has to carry what happened
    body = (
        f"Room code: {code}\n"
        "What happened:\n\n\n"
        "If you can, attach a screenshot. Messages are end-to-end encrypted, "
        "so nobody else can see them."
    )
    return f"mailto:{REPORT_EMAIL}?subject={quote('Report: Cipher')}&body={quote(body)}"


@cache
def _file_hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:10]


def create_app() -> Flask:
    app = Flask(__name__, static_url_path='/cipher/static')
    app.config.from_object(Config)

    # No cors_allowed_origins: Socket.IO then only accepts same-origin connections.
    # 16 KB per packet is plenty for a 1000-character message.
    socketio.init_app(app, async_mode="eventlet", path="/cipher/socket.io",
                      max_http_buffer_size=16_384)
    limiter.init_app(app)

    # Behind cloudflared -> nginx, Flask sees plain http. Trust the one proxy's
    # X-Forwarded-Proto so redirects (e.g. /cipher -> /cipher/) stay on https.
    # x_for=0: client IPs come from CF-Connecting-IP (see extensions.py), not X-Forwarded-For.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    # Inject csrf_token() into every template
    app.jinja_env.globals["csrf_token"] = _csrf.token

    # asset('js/room.js') -> /cipher/static/js/room.js?v=<content hash>, so a
    # deploy never leaves Cloudflare or a browser serving an old copy
    def asset(filename: str) -> str:
        path = str(Path(app.static_folder) / filename)
        v = _file_hash.__wrapped__(path) if app.debug else _file_hash(path)
        return url_for("static", filename=filename, v=v)
    app.jinja_env.globals["asset"] = asset
    app.jinja_env.globals.update(
        terms_url=TERMS_URL, privacy_url=PRIVACY_URL,
        reporting_url=REPORTING_URL, report_mailto=report_mailto,
    )

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if response.mimetype == "text/html":
            # Don't leave room pages in the browser's disk or back/forward cache
            response.headers["Cache-Control"] = "no-store"
        return response

    from app.routes.home import home_bp
    from app.routes.room import room_bp
    app.register_blueprint(home_bp, url_prefix='/cipher')
    app.register_blueprint(room_bp, url_prefix='/cipher')
    # Outside /cipher on purpose: nginx never forwards it (see app/operator.py)
    from app.operator import operator_bp
    app.register_blueprint(operator_bp)

    with app.app_context():
        from app.sockets import events
    # Cap sockets per visitor before Socket.IO even sees them, and the
    # requests hanging off them (outermost, so it counts everything)
    events.guard_engineio(socketio.server.eio)
    app.wsgi_app = events.cap_requests(app.wsgi_app)

    return app
