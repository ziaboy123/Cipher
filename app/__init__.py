from flask import Flask
from app.config import config
from app.extensions import db, login_manager, bcrypt, csrf, limiter, migrate, socketio


def create_app(env: str = "default") -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[env])

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(users_bp)

    # Socket events
    with app.app_context():
        from app.sockets import events as _  # noqa: F401
        db.create_all()

    return app
