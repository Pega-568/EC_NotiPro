from flask import current_app

from app.extensions import db
from app.constants import ROLE_ADMIN, ROLE_AGENDADOR, ROLE_COLABORADOR, ROLE_SECRETARIA
from app.models import Area, Configuracion, Role, Usuario, ZonaReunion
from app.security import hash_password


DEFAULT_CONFIG = {
    "descanso_persona_minutos": ("10", "Minutos de descanso entre reuniones por persona."),
    "margen_zona_minutos": ("5", "Margen operativo global para zonas."),
    "horario_laboral_inicio": ("08:00", "Hora de inicio laboral."),
    "horario_laboral_fin": ("17:00", "Hora de fin laboral."),
    "max_intentos_login": ("5", "Intentos maximos de login antes de bloqueo temporal."),
    "debug_mode": ("false", "Controla la visualizacion de datos tecnicos en interfaces."),
    "recordatorio_30_minutos": ("true", "Activa recordatorio 30 minutos antes."),
    "recordatorio_10_minutos": ("true", "Activa recordatorio 10 minutos antes."),
    "correo_formal_automatico": ("true", "Activa los correos formales automaticos."),
}

DEFAULT_ZONES = [
    ("Sala Principal", "Piso 1", 20, None, "Activa", 5),
    ("Sala Contabilidad", "Piso 2", 8, "Contabilidad", "Activa", 5),
    ("Sala Administracion", "Piso 3", 10, "Administracion", "Activa", 5),
]


def seed_base_defaults() -> dict[str, object]:
    role_aliases = {
        "Admin": ROLE_ADMIN,
        "Agendador": ROLE_AGENDADOR,
        "Usuario natural": ROLE_COLABORADOR,
    }
    for legacy_name, role_name in role_aliases.items():
        legacy = Role.query.filter_by(nombre=legacy_name).first()
        if legacy:
            legacy.nombre = role_name
    for role_name in (ROLE_ADMIN, ROLE_AGENDADOR, ROLE_SECRETARIA, ROLE_COLABORADOR):
        if not Role.query.filter_by(nombre=role_name).first():
            db.session.add(Role(nombre=role_name))
    db.session.flush()

    areas = {}
    for area_name in ("Contabilidad", "Mercado Privado", "Administracion", "Soporte Tecnico"):
        area = Area.query.filter_by(nombre=area_name).first()
        if not area:
            area = Area(nombre=area_name, estado="Activa")
            db.session.add(area)
            db.session.flush()
        elif not area.estado:
            area.estado = "Activa"
        areas[area_name] = area

    for key, (value, description) in DEFAULT_CONFIG.items():
        if not Configuracion.query.filter_by(clave=key).first():
            db.session.add(Configuracion(clave=key, valor=value, descripcion=description))

    admin_role = Role.query.filter_by(nombre=ROLE_ADMIN).first()
    scheduler_role = Role.query.filter_by(nombre=ROLE_SECRETARIA).first()
    agendador_role = Role.query.filter_by(nombre=ROLE_AGENDADOR).first()
    user_role = Role.query.filter_by(nombre=ROLE_COLABORADOR).first()

    return {
        "areas": areas,
        "roles": {
            "admin": admin_role,
            "secretaria": scheduler_role,
            "agendador": agendador_role,
            "colaborador": user_role,
        },
    }


def seed_demo_users(seed_context: dict[str, object]) -> None:
    areas = seed_context["areas"]
    roles = seed_context["roles"]

    users = [
        ("Administrador Principal", "admin@empresa.local", "Admin123!", roles["admin"].id, areas["Contabilidad"].id),
        (
            "Secretaria General",
            "secretaria.general@empresa.local",
            "Agenda123!",
            roles["secretaria"].id,
            areas["Contabilidad"].id,
        ),
        (
            "Agendador Contabilidad",
            "agendador.contabilidad@empresa.local",
            "Agenda123!",
            roles["agendador"].id,
            areas["Contabilidad"].id,
        ),
        (
            "Colaborador 1 Contabilidad",
            "usuario1.contabilidad@empresa.local",
            "Usuario123!",
            roles["colaborador"].id,
            areas["Contabilidad"].id,
        ),
        (
            "Colaborador 2 Contabilidad",
            "usuario2.contabilidad@empresa.local",
            "Usuario123!",
            roles["colaborador"].id,
            areas["Contabilidad"].id,
        ),
        (
            "Colaborador 1 Mercado",
            "usuario1.mercado@empresa.local",
            "Usuario123!",
            roles["colaborador"].id,
            areas["Mercado Privado"].id,
        ),
    ]
    for nombre, correo, password, role_id, area_id in users:
        if not Usuario.query.filter_by(correo=correo).first():
            db.session.add(
                Usuario(
                    nombre=nombre,
                    correo=correo,
                    telefono=None,
                    password_hash=hash_password(password),
                    role_id=role_id,
                    area_id=area_id,
                )
            )


def seed_base_zones(seed_context: dict[str, object]) -> None:
    areas = seed_context["areas"]
    for nombre, ubicacion, capacidad, area_name, estado, margen in DEFAULT_ZONES:
        area_id = areas[area_name].id if area_name else None
        if not ZonaReunion.query.filter_by(nombre=nombre).first():
            db.session.add(
                ZonaReunion(
                    nombre=nombre,
                    ubicacion=ubicacion,
                    capacidad=capacidad,
                    area_id=area_id,
                    estado=estado,
                    margen_operativo_minutos=margen,
                )
            )


def seed_defaults() -> None:
    seed_context = seed_base_defaults()
    app_env = current_app.config.get("APP_ENV", "development")
    allow_demo_seed = current_app.config.get("ALLOW_DEMO_SEED", False)
    seed_base_zones(seed_context)
    if app_env != "production" and (allow_demo_seed or app_env in {"development", "testing", "staging"}):
        seed_demo_users(seed_context)
    db.session.commit()
