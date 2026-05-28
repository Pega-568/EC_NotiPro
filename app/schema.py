from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db


def ensure_runtime_schema() -> None:
    inspector = inspect(db.engine)

    if "areas" in inspector.get_table_names():
        area_columns = {column["name"] for column in inspector.get_columns("areas")}
        if "estado" not in area_columns:
            db.session.execute(
                text("ALTER TABLE areas ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'Activa'")
            )
            db.session.commit()

    if "usuarios" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
        if "telefono" not in user_columns:
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(30)"))
            db.session.commit()

    if "logs_sistema" in inspector.get_table_names():
        log_columns = {column["name"] for column in inspector.get_columns("logs_sistema")}
        if "descripcion_humana" not in log_columns:
            db.session.execute(text("ALTER TABLE logs_sistema ADD COLUMN descripcion_humana VARCHAR(1000)"))
            db.session.commit()
