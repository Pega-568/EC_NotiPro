from app.extensions import db
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
}


def seed_defaults() -> None:
    for role_name in ("Admin", "Agendador", "Usuario natural"):
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

    admin_role = Role.query.filter_by(nombre="Admin").first()
    scheduler_role = Role.query.filter_by(nombre="Agendador").first()
    user_role = Role.query.filter_by(nombre="Usuario natural").first()

    users = [
        ("Admin Principal", "admin@empresa.local", "Admin123!", admin_role.id, areas["Contabilidad"].id),
        (
            "Agendador Contabilidad",
            "agendador.contabilidad@empresa.local",
            "Agenda123!",
            scheduler_role.id,
            areas["Contabilidad"].id,
        ),
        (
            "Usuario 1 Contabilidad",
            "usuario1.contabilidad@empresa.local",
            "Usuario123!",
            user_role.id,
            areas["Contabilidad"].id,
        ),
        (
            "Usuario 2 Contabilidad",
            "usuario2.contabilidad@empresa.local",
            "Usuario123!",
            user_role.id,
            areas["Contabilidad"].id,
        ),
        (
            "Usuario 1 Mercado",
            "usuario1.mercado@empresa.local",
            "Usuario123!",
            user_role.id,
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

    zones = [
        ("Sala Principal", "Piso 1", 20, None, "Activa", 5),
        ("Sala Contabilidad", "Piso 2", 8, areas["Contabilidad"].id, "Activa", 5),
        ("Sala Administracion", "Piso 3", 10, areas["Administracion"].id, "Activa", 5),
    ]
    for nombre, ubicacion, capacidad, area_id, estado, margen in zones:
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
    db.session.commit()
