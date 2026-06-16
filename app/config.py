import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-in-production"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///cipher.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Session hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set True when running HTTPS

    # Flask-Limiter storage
    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")

    # WTF
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
