import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///agenda.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
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
    FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "").strip()
    FCM_ENDPOINT = os.getenv("FCM_ENDPOINT", "https://fcm.googleapis.com/fcm/send").strip()


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
