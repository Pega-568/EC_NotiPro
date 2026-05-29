from __future__ import annotations

from sqlalchemy import text

from flask import Flask, jsonify, request

from app.config import Config, TestConfig
from app.constants import ROLE_ADMIN
from app.extensions import db, migrate
from app.models import Area, Role, Usuario
from app.security import hash_password


def create_app(config_object=None) -> Flask:
    # Import heavier modules lazily to avoid circular import issues during test discovery
    from app.api.routes import api_bp
    from app.auth import enforce_csrf, load_current_user
    from app.audit import log_event
    from app.errors import AppError, ValidationError
    from app.services.notifications import dispatch_due_communications, start_background_dispatcher
    from app.services.seeds import seed_defaults
    from app.web import web_bp

    app = Flask(__name__)
    if config_object == "testing":
        app.config.from_object(TestConfig)
    elif config_object:
        app.config.from_object(config_object)
    else:
        app.config.from_object(Config)

    Config.validate_runtime_or_raise(app.config.get("debug_mode", "false"))

    db.init_app(app)
    migrate.init_app(app, db)

    @app.before_request
    def before_request():
        load_current_user()
        enforce_csrf()

    @app.after_request
    def apply_cors(response):
        origin = request.headers.get("Origin")
        if origin and origin in app.config["APP_ALLOWED_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError):
        if request.path.startswith("/api/") and isinstance(exc, ValidationError):
            log_event(
                "error_validacion",
                "request",
                "rechazado",
                detail={"ruta": request.path, "error": exc.message},
            )
            db.session.commit()
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "error": exc.error,
                        "message": exc.message,
                    }
                ),
                exc.status_code,
            )
        return jsonify({"error": exc.message}), exc.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        db.session.rollback()
        try:
            log_event("error_sistema", "backend", "fallido", detail={"ruta": request.path, "error": str(exc)})
            db.session.commit()
        except Exception:
            db.session.rollback()
            
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    {
                        "error": "internal_server_error",
                        "message": "Ocurrio un error interno.",
                    }
                ),
                500,
            )
        return jsonify({"error": "Ocurrio un error interno."}), 500

    @app.get("/health")
    def health():
        fcm_configured = bool(
            app.config.get("FCM_ENABLED") and app.config.get("FCM_SERVICE_ACCOUNT_PATH")
        )
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "status": "degraded",
                        "database": "error",
                        "fcm_configured": fcm_configured,
                        "app_env": app.config.get("APP_ENV", "development"),
                    }
                ),
                503,
            )
        return jsonify(
            {
                "status": "ok",
                "database": "ok",
                "fcm_configured": fcm_configured,
                "app_env": app.config.get("APP_ENV", "development"),
            }
        )

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    with app.app_context():
        if app.config.get("TESTING"):
            db.create_all()
    start_background_dispatcher(app)

    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
            seed_defaults()
            if app.config.get("APP_ENV") == "production":
                print("Base de datos inicializada con catalogos base. No se crearon usuarios demo.")
            else:
                print("Base de datos inicializada con datos semilla.")

    @app.cli.command("create-admin")
    def create_admin_command():
        admin_email = (app.config.get("ADMIN_EMAIL") or "").strip().lower()
        admin_password = app.config.get("ADMIN_PASSWORD") or ""
        admin_name = (app.config.get("ADMIN_NAME") or "").strip()

        if not admin_email:
            raise RuntimeError("ADMIN_EMAIL is required.")
        if not admin_password:
            raise RuntimeError("ADMIN_PASSWORD is required.")
        if len(admin_password) < 12 or admin_password.lower() in {
            "admin123!",
            "password",
            "123456",
            "12345678",
            "qwerty",
        }:
            raise RuntimeError("ADMIN_PASSWORD is too weak.")
        if not admin_name:
            admin_name = "Administrador Principal"

        with app.app_context():
            admin_role = Role.query.filter_by(nombre=ROLE_ADMIN).first()
            if not admin_role:
                raise RuntimeError("Admin role does not exist. Run flask init-db first.")

            area = Area.query.filter_by(nombre="Administracion").first()
            if not area:
                area = Area(nombre="Administracion", estado="Activa")
                db.session.add(area)
                db.session.flush()

            user = Usuario.query.filter_by(correo=admin_email).first()
            if user:
                user.nombre = admin_name
                user.password_hash = hash_password(admin_password)
                user.role_id = admin_role.id
                user.area_id = area.id
                user.estado = "Activo"
            else:
                user = Usuario(
                    nombre=admin_name,
                    correo=admin_email,
                    telefono=None,
                    password_hash=hash_password(admin_password),
                    role_id=admin_role.id,
                    area_id=area.id,
                )
                db.session.add(user)
            db.session.commit()
            print(f"Administrador seguro listo: {admin_email}")

    @app.cli.command("dispatch-notifications")
    def dispatch_notifications_command():
        with app.app_context():
            processed = dispatch_due_communications()
            db.session.commit()
            print(
                f"Eventos procesados: push={processed['push']}, email={processed['email']}"
            )

    return app
