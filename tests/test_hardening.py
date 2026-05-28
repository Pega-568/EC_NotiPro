import pytest

from app.config import Config


def test_validate_runtime_rechaza_secret_key_inseguro(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", "change-me")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "postgresql+psycopg://demo")
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(Config, "INTERNAL_BASE_URL", "https://notipro.interno")
    with pytest.raises(RuntimeError):
        Config.validate_runtime_or_raise("false")


def test_validate_runtime_rechaza_sqlite_en_produccion(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "staging")
    monkeypatch.setattr(Config, "SECRET_KEY", "segura")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///agenda.db")
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(Config, "INTERNAL_BASE_URL", "https://notipro.interno")
    with pytest.raises(RuntimeError):
        Config.validate_runtime_or_raise("false")


def test_validate_runtime_exige_cookie_secure(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", "segura")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "postgresql+psycopg://demo")
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(Config, "INTERNAL_BASE_URL", "https://notipro.interno")
    with pytest.raises(RuntimeError):
        Config.validate_runtime_or_raise("false")


def test_validate_runtime_rechaza_internal_base_url_local(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", "segura")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "postgresql+psycopg://demo")
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(Config, "INTERNAL_BASE_URL", "http://127.0.0.1:5000")
    with pytest.raises(RuntimeError):
        Config.validate_runtime_or_raise("false")


def test_validate_runtime_rechaza_debug_mode_activo(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", "segura")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "postgresql+psycopg://demo")
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(Config, "INTERNAL_BASE_URL", "https://notipro.interno")
    with pytest.raises(RuntimeError):
        Config.validate_runtime_or_raise("true")
