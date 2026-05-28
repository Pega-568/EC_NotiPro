import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from flask import current_app

from app.extensions import db
from app.models import UserSession, Usuario


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False


def issue_session(user: Usuario) -> tuple[str, str, UserSession]:
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = UserSession(
        usuario_id=user.id,
        token_hash=token_hash,
        csrf_token=csrf_token,
        expira_en=datetime.utcnow()
        + timedelta(minutes=current_app.config["SESSION_TTL_MINUTES"]),
        activa=True,
    )
    db.session.add(session)
    db.session.flush()
    return raw_token, csrf_token, session


def get_session_by_token(raw_token: str | None) -> UserSession | None:
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = UserSession.query.filter_by(token_hash=token_hash, activa=True).first()
    if not session or session.expira_en <= datetime.utcnow():
        return None
    return session


def revoke_session(raw_token: str | None) -> None:
    session = get_session_by_token(raw_token)
    if session:
        session.activa = False
        db.session.commit()

