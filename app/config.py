import os
from dotenv import load_dotenv

load_dotenv()

# Production is the default. CIPHER_DEV=1 (local previews only) turns on debug
# and allows the session cookie over plain http://localhost.
DEV = os.environ.get("CIPHER_DEV") == "1"

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if not DEV:
        raise RuntimeError("SECRET_KEY is not set. Put it in .env (see .env.example).")
    SECRET_KEY = "dev-only-change-me"


class Config:
    SECRET_KEY = SECRET_KEY
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEV
    DEBUG = DEV
