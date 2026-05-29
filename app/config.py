import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///agenda.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    }
    SESSION_COOKIE_NAME = "agenda_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    APP_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("APP_ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
        if origin.strip()
    ]
    SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "480"))
    LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
    FCM_ENABLED = os.getenv("FCM_ENABLED", "false").lower() == "true"
    FCM_SERVICE_ACCOUNT_PATH = os.getenv("FCM_SERVICE_ACCOUNT_PATH", "").strip()
    MAIL_ENABLED = os.getenv("MAIL_ENABLED", "false").lower() == "true"
    MAIL_HOST = os.getenv("MAIL_HOST", "").strip()
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_FROM = os.getenv("MAIL_FROM", "notificaciones@ecuamatriz.local").strip()
    MAIL_REPLY_TO = os.getenv("MAIL_REPLY_TO", MAIL_FROM).strip()
    MAIL_SUBJECT_PREFIX = os.getenv("MAIL_SUBJECT_PREFIX", "[Ecuamatriz]").strip()
    INTERNAL_BASE_URL = os.getenv("INTERNAL_BASE_URL", "http://127.0.0.1:5000").strip()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    LOG_FILE = os.getenv("LOG_FILE", "").strip()
    ALLOW_DEMO_SEED = os.getenv("ALLOW_DEMO_SEED", "false").lower() == "true"
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
    ADMIN_NAME = os.getenv("ADMIN_NAME", "").strip()
    BACKGROUND_DISPATCH_ENABLED = os.getenv("BACKGROUND_DISPATCH_ENABLED", "false").lower() == "true"
    BACKGROUND_DISPATCH_INTERVAL_SECONDS = int(
        os.getenv("BACKGROUND_DISPATCH_INTERVAL_SECONDS", "30")
    )

    @classmethod
    def validate_runtime_or_raise(cls, debug_mode: str) -> None:
        if cls.APP_ENV in ("production", "staging"):
            secret_key = (cls.SECRET_KEY or "").strip()
            if not secret_key or secret_key in {"change-me", "change-me-in-production"}:
                raise RuntimeError("Insecure SECRET_KEY for production.")
            if "sqlite" in (cls.SQLALCHEMY_DATABASE_URI or "").lower():
                raise RuntimeError("SQLite cannot be used in production.")
            if not cls.SESSION_COOKIE_SECURE:
                raise RuntimeError("SESSION_COOKIE_SECURE must be True in production.")
            internal_base_url = cls.INTERNAL_BASE_URL.lower()
            if "127.0.0.1" in internal_base_url or "localhost" in internal_base_url:
                raise RuntimeError("INTERNAL_BASE_URL must not be local in production.")
            if not cls.APP_ALLOWED_ORIGINS:
                raise RuntimeError("APP_ALLOWED_ORIGINS must not be empty in production.")
            lowered_origins = [origin.lower() for origin in cls.APP_ALLOWED_ORIGINS]
            if any("127.0.0.1" in origin or "localhost" in origin for origin in lowered_origins):
                raise RuntimeError("APP_ALLOWED_ORIGINS must not contain local hosts in production.")
            if cls.FCM_ENABLED:
                if not cls.FCM_SERVICE_ACCOUNT_PATH:
                    raise RuntimeError("FCM_SERVICE_ACCOUNT_PATH is required when FCM_ENABLED=true.")
                if not Path(cls.FCM_SERVICE_ACCOUNT_PATH).is_file():
                    raise RuntimeError("FCM_SERVICE_ACCOUNT_PATH does not exist.")
            if cls.ALLOW_DEMO_SEED:
                raise RuntimeError("ALLOW_DEMO_SEED must be False in production.")
            if debug_mode.lower() == "true":
                raise RuntimeError("Debug mode must be disabled in production.")


class TestConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    FCM_ENABLED = False
    MAIL_ENABLED = False
    BACKGROUND_DISPATCH_ENABLED = False
