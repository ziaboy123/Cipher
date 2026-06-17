from flask import Flask
from app.config import Config
from app.extensions import socketio, limiter
from app import csrf as _csrf


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    socketio.init_app(app, async_mode="eventlet", cors_allowed_origins="*")
    limiter.init_app(app)

    # Inject csrf_token() into every template
    app.jinja_env.globals["csrf_token"] = _csrf.token

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    from app.routes.home import home_bp
    from app.routes.room import room_bp
    app.register_blueprint(home_bp)
    app.register_blueprint(room_bp)

    with app.app_context():
        from app.sockets import events as _  # noqa: F401

    return app
