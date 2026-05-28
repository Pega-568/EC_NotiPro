from __future__ import annotations

from flask import Flask, jsonify, request

from app.api.routes import api_bp
from app.auth import enforce_csrf, load_current_user
from app.config import Config, TestConfig
from app.audit import log_event
from app.errors import AppError, ValidationError
from app.extensions import db
from app.schema import ensure_runtime_schema
from app.services.notifications import dispatch_pending_notifications
from app.services.seeds import seed_defaults
from app.web import web_bp


def create_app(config_object=None) -> Flask:
    app = Flask(__name__)
    if config_object == "testing":
        app.config.from_object(TestConfig)
    elif config_object:
        app.config.from_object(config_object)
    else:
        app.config.from_object(Config)

    db.init_app(app)

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
        db.create_all()
        ensure_runtime_schema()

    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
            ensure_runtime_schema()
            seed_defaults()
            print("Base de datos inicializada con datos semilla.")

    @app.cli.command("dispatch-notifications")
    def dispatch_notifications_command():
        with app.app_context():
            processed = dispatch_pending_notifications()
            db.session.commit()
            print(f"Eventos procesados: {processed}")

    return app
