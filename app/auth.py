from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, url_for

from app.audit import log_event
from app.errors import AuthenticationError, ForbiddenError
from app.extensions import db
from app.models import Usuario
from app.security import get_session_by_token


def load_current_user() -> None:
    g.current_user = None
    g.current_session = None
    g.auth_scheme = None
    raw_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header.removeprefix("Bearer ").strip()
        g.auth_scheme = "bearer"
    else:
        raw_token = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
        if raw_token:
            g.auth_scheme = "cookie"
    session = get_session_by_token(raw_token)
    if not session:
        return
    user = session.usuario
    if user.estado != "Activo":
        return
    session.expira_en = datetime.utcnow() + timedelta(
        minutes=current_app.config["SESSION_TTL_MINUTES"]
    )
    db.session.add(session)
    g.current_user = user
    g.current_session = session


def require_auth(api: bool = True):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(g, "current_user", None):
                if api:
                    raise AuthenticationError("Debe iniciar sesion.")
                return redirect(url_for("web.login"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_roles(*allowed_roles: str, api: bool = True):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                if api:
                    raise AuthenticationError("Debe iniciar sesion.")
                return redirect(url_for("web.login"))
            if user.role.nombre not in allowed_roles:
                log_event(
                    "intento_no_autorizado",
                    "permiso",
                    "rechazado",
                    detail={
                        "ruta": request.path,
                        "rol": user.role.nombre,
                        "accion_intentada": request.endpoint or request.path,
                    },
                )
                db.session.commit()
                raise ForbiddenError("No tiene permiso para realizar esta accion.")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def enforce_csrf() -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.endpoint == "api.login":
        return
    if request.endpoint == "api.mobile_login":
        return
    if getattr(g, "auth_scheme", None) == "bearer":
        return
    if not getattr(g, "current_session", None):
        return
    candidate = request.headers.get("X-CSRF-Token")
    if not candidate and request.form:
        candidate = request.form.get("csrf_token")
    if candidate != g.current_session.csrf_token:
        raise ForbiddenError("Token CSRF invalido.")


def set_session_cookies(response, session_token: str, csrf_token: str):
    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME"],
        session_token,
        httponly=True,
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite=current_app.config["SESSION_COOKIE_SAMESITE"],
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite=current_app.config["SESSION_COOKIE_SAMESITE"],
    )
    return response


def clear_session_cookies(response):
    response.delete_cookie(current_app.config["SESSION_COOKIE_NAME"])
    response.delete_cookie("csrf_token")
    return response
