from __future__ import annotations

from flask import Flask, jsonify, request

from app.config import Config, TestConfig
from app.extensions import db, migrate


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
            print("Base de datos inicializada con datos semilla.")

    @app.cli.command("dispatch-notifications")
    def dispatch_notifications_command():
        with app.app_context():
            processed = dispatch_due_communications()
            db.session.commit()
            print(
                f"Eventos procesados: push={processed['push']}, email={processed['email']}"
            )

    return app
