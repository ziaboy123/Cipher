from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
migrate = Migrate()
socketio = SocketIO()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)

login_manager.login_view = "auth.login"
login_manager.login_message = None
