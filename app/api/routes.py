from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, make_response, request

from app.audit import log_event
from app.auth import clear_session_cookies, require_auth, require_roles, set_session_cookies
from app.errors import AuthenticationError, ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Area, Configuracion, DeviceToken, LogSistema, Reunion, Role, Usuario, ZonaReunion
from app.permissions import ensure_meeting_access
from app.security import hash_password, issue_session, verify_password
from app.services.meetings import (
    cancel_meeting,
    create_meeting,
    respond_to_meeting,
    serialize_meeting,
    update_meeting,
)
from app.services.notifications import register_device_token


api_bp = Blueprint("api", __name__, url_prefix="/api")


def _user_payload(user: Usuario) -> dict:
    return {
        "id": user.id,
        "nombre": user.nombre,
        "correo": user.correo,
        "estado": user.estado,
        "role": user.role.nombre,
        "area": {"id": user.area.id, "nombre": user.area.nombre},
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _zone_payload(zone: ZonaReunion) -> dict:
    return {
        "id": zone.id,
        "nombre": zone.nombre,
        "ubicacion": zone.ubicacion,
        "capacidad": zone.capacidad,
        "area_id": zone.area_id,
        "estado": zone.estado,
        "margen_operativo_minutos": zone.margen_operativo_minutos,
        "descripcion": zone.descripcion,
        "created_at": zone.created_at.isoformat(),
        "updated_at": zone.updated_at.isoformat(),
    }


def _mobile_meeting_payload(meeting: Reunion, viewer: Usuario) -> dict:
    participant = next((item for item in meeting.participantes if item.usuario_id == viewer.id), None)
    accepted = sum(1 for item in meeting.participantes if item.estado_respuesta == "Aceptada")
    rejected = sum(1 for item in meeting.participantes if item.estado_respuesta == "Rechazada")
    pending = sum(1 for item in meeting.participantes if item.estado_respuesta == "Pendiente")
    return {
        "id": meeting.id,
        "titulo": meeting.titulo,
        "motivo": meeting.motivo,
        "fecha": meeting.fecha.isoformat(),
        "hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
        "hora_fin": meeting.hora_fin.strftime("%H:%M"),
        "estado": meeting.estado,
        "estado_visual": serialize_meeting(meeting)["estado_visual"],
        "prioridad": meeting.prioridad,
        "zona": {"id": meeting.zona.id, "nombre": meeting.zona.nombre, "ubicacion": meeting.zona.ubicacion},
        "creador": {"id": meeting.creador.id, "nombre": meeting.creador.nombre},
        "mi_respuesta": participant.estado_respuesta if participant else None,
        "mi_razon_rechazo": participant.razon_rechazo if participant else None,
        "resumen_respuestas": {"aceptadas": accepted, "rechazadas": rejected, "pendientes": pending},
        "participantes": [
            {
                "usuario_id": item.usuario_id,
                "nombre": item.usuario.nombre,
                "correo": item.usuario.correo,
                "estado_respuesta": item.estado_respuesta,
                "razon_rechazo": item.razon_rechazo,
            }
            for item in meeting.participantes
        ],
    }


@api_bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    correo = (payload.get("correo") or "").strip().lower()
    password = payload.get("password") or ""
    if not correo or not password:
        raise ValidationError("correo y password son obligatorios.")
    user = Usuario.query.filter_by(correo=correo).first()
    max_attempts = int(
        (Configuracion.query.filter_by(clave="max_intentos_login").first() or Configuracion(valor="5")).valor
    )
    if not user:
        log_event("login_fallido", "auth", "rechazado", detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    if user.estado != "Activo":
        log_event("login_fallido", "auth", "rechazado", entity_id=user.id, detail={"motivo": "usuario_inactivo"})
        db.session.commit()
        raise AuthenticationError("Usuario inactivo.")
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise AuthenticationError("Usuario bloqueado temporalmente por intentos fallidos.")
    if not verify_password(user.password_hash, password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.utcnow().replace(microsecond=0) + timedelta(
                minutes=current_app.config["LOGIN_LOCK_MINUTES"]
            )
        log_event("login_fallido", "auth", "rechazado", entity_id=user.id, detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    user.failed_login_attempts = 0
    user.locked_until = None
    user.ultimo_login_at = datetime.utcnow()
    session_token, csrf_token, session = issue_session(user)
    log_event("login", "auth", "exitoso", entity_id=user.id)
    db.session.commit()
    response = make_response(
        jsonify(
            {
                "message": "Login exitoso.",
                "csrf_token": csrf_token,
                "user": _user_payload(user),
            }
        )
    )
    return set_session_cookies(response, session_token, csrf_token)


@api_bp.post("/auth/logout")
@require_auth()
def logout():
    g.current_session.activa = False
    log_event("logout", "auth", "exitoso", entity_id=g.current_user.id)
    db.session.commit()
    response = make_response(jsonify({"message": "Sesion cerrada."}))
    return clear_session_cookies(response)


@api_bp.get("/auth/me")
@require_auth()
def me():
    return jsonify({"user": _user_payload(g.current_user)})


@api_bp.post("/mobile/device-token")
@require_auth()
def mobile_register_device_token():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        raise ValidationError("token es obligatorio.")
    device = register_device_token(
        user_id=g.current_user.id,
        token=token,
        plataforma="android",
        app_version=payload.get("app_version"),
        debug_ui=bool(payload.get("debug_ui", False)),
    )
    log_event(
        "registro_device_token",
        "device_token",
        "exitoso",
        entity_id=device.id,
        detail={"target_user_nombre": g.current_user.nombre},
    )
    db.session.commit()
    return jsonify({"id": device.id, "estado": device.estado})


@api_bp.get("/usuarios")
@require_auth()
def list_users():
    user = g.current_user
    query = Usuario.query
    if user.role.nombre == "Admin":
        users = query.order_by(Usuario.id).all()
    elif user.role.nombre == "Agendador":
        users = query.filter_by(area_id=user.area_id).order_by(Usuario.id).all()
    else:
        raise ForbiddenError("No tiene permiso para listar usuarios.")
    return jsonify({"items": [_user_payload(item) for item in users]})


@api_bp.get("/usuarios/buscar")
@require_auth()
def search_users():
    actor = g.current_user
    if actor.role.nombre not in ("Admin", "Agendador"):
        raise ForbiddenError("No tiene permiso para buscar usuarios.")
    q = (request.args.get("q") or "").strip().lower()
    area_id_raw = request.args.get("area_id")
    if actor.role.nombre == "Agendador":
        if area_id_raw and int(area_id_raw) != actor.area_id:
            raise ForbiddenError("Agendador solo puede buscar usuarios de su area.")
        area_id = actor.area_id
    else:
        area_id = int(area_id_raw) if area_id_raw else None
    query = Usuario.query.filter_by(estado="Activo")
    if area_id:
        query = query.filter_by(area_id=area_id)
    if q:
        like = f"%{q}%"
        query = query.filter((Usuario.nombre.ilike(like)) | (Usuario.correo.ilike(like)))
    users = query.order_by(Usuario.nombre).limit(20).all()
    return jsonify(
        [
            {
                "id": user.id,
                "nombre": user.nombre,
                "correo": user.correo,
                "area": user.area.nombre,
                "rol": user.role.nombre,
                "estado": user.estado,
            }
            for user in users
        ]
    )


@api_bp.post("/mobile/auth/login")
def mobile_login():
    payload = request.get_json(silent=True) or {}
    correo = (payload.get("correo") or "").strip().lower()
    password = payload.get("password") or ""
    if not correo or not password:
        raise ValidationError("correo y password son obligatorios.")
    user = Usuario.query.filter_by(correo=correo).first()
    max_attempts = int(
        (Configuracion.query.filter_by(clave="max_intentos_login").first() or Configuracion(valor="5")).valor
    )
    if not user:
        log_event("login_fallido", "auth_mobile", "rechazado", detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    if user.estado != "Activo":
        log_event("login_fallido", "auth_mobile", "rechazado", entity_id=user.id, detail={"motivo": "usuario_inactivo"})
        db.session.commit()
        raise AuthenticationError("Usuario inactivo.")
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise AuthenticationError("Usuario bloqueado temporalmente por intentos fallidos.")
    if not verify_password(user.password_hash, password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.utcnow() + timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
        log_event("login_fallido", "auth_mobile", "rechazado", entity_id=user.id, detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    user.failed_login_attempts = 0
    user.locked_until = None
    user.ultimo_login_at = datetime.utcnow()
    access_token, csrf_token, session = issue_session(user)
    log_event("login", "auth_mobile", "exitoso", entity_id=user.id)
    db.session.commit()
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in_minutes": current_app.config["SESSION_TTL_MINUTES"],
            "user": _user_payload(user),
        }
    )


@api_bp.get("/mobile/auth/me")
@require_auth()
def mobile_me():
    return jsonify({"user": _user_payload(g.current_user)})


@api_bp.post("/mobile/auth/logout")
@require_auth()
def mobile_logout():
    g.current_session.activa = False
    log_event("logout", "auth_mobile", "exitoso", entity_id=g.current_user.id)
    db.session.commit()
    return jsonify({"message": "Sesion cerrada."})


@api_bp.get("/mobile/reuniones")
@require_auth()
def mobile_meetings():
    meetings = (
        Reunion.query.filter(Reunion.participantes.any(usuario_id=g.current_user.id))
        .order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc())
        .all()
    )
    return jsonify({"items": [_mobile_meeting_payload(meeting, g.current_user) for meeting in meetings]})


@api_bp.get("/mobile/reuniones/<int:meeting_id>")
@require_auth()
def mobile_meeting_detail(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    return jsonify(_mobile_meeting_payload(meeting, g.current_user))


@api_bp.post("/mobile/reuniones/<int:meeting_id>/aceptar")
@require_auth()
def mobile_accept_meeting(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    respond_to_meeting(meeting, accept=True)
    return jsonify(_mobile_meeting_payload(meeting, g.current_user))


@api_bp.post("/mobile/reuniones/<int:meeting_id>/rechazar")
@require_auth()
def mobile_reject_meeting(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    payload = request.get_json(silent=True) or {}
    respond_to_meeting(meeting, accept=False, reason=payload.get("razon"))
    return jsonify(_mobile_meeting_payload(meeting, g.current_user))


@api_bp.post("/usuarios")
@require_roles("Admin")
def create_user():
    payload = request.get_json(silent=True) or {}
    required = ("nombre", "correo", "password", "role_id", "area_id")
    if any(not payload.get(field) for field in required):
        raise ValidationError("nombre, correo, password, role_id y area_id son obligatorios.")
    if Usuario.query.filter_by(correo=payload["correo"].strip().lower()).first():
        raise ValidationError("El correo ya existe.")
    role_id = int(payload["role_id"])
    area_id = int(payload["area_id"])
    if not Role.query.get(role_id):
        raise ValidationError("Rol invalido.")
    if not Area.query.get(area_id):
        raise ValidationError("Area invalida.")
    user = Usuario(
        nombre=payload["nombre"].strip(),
        correo=payload["correo"].strip().lower(),
        password_hash=hash_password(payload["password"]),
        role_id=role_id,
        area_id=area_id,
    )
    db.session.add(user)
    db.session.flush()
    log_event(
        "creacion_usuario",
        "usuario",
        "exitoso",
        entity_id=user.id,
        detail={
            "target_user_nombre": user.nombre,
            "area_nombre": user.area.nombre,
            "role_nombre": user.role.nombre,
        },
    )
    db.session.commit()
    return jsonify(_user_payload(user)), 201


@api_bp.patch("/usuarios/<int:user_id>")
@require_roles("Admin")
def update_user(user_id: int):
    payload = request.get_json(silent=True) or {}
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    if "nombre" in payload:
        user.nombre = payload["nombre"].strip()
    if "area_id" in payload:
        area = Area.query.get(int(payload["area_id"]))
        if not area:
            raise ValidationError("Area invalida.")
        user.area_id = area.id
    if "role_id" in payload:
        role = Role.query.get(int(payload["role_id"]))
        if not role:
            raise ValidationError("Rol invalido.")
        user.role_id = role.id
    if "estado" in payload and payload["estado"] in ("Activo", "Inactivo"):
        user.estado = payload["estado"]
    log_event(
        "edicion_usuario",
        "usuario",
        "exitoso",
        entity_id=user.id,
        detail={"target_user_nombre": user.nombre},
    )
    db.session.commit()
    return jsonify(_user_payload(user))


@api_bp.patch("/usuarios/<int:user_id>/desactivar")
@require_roles("Admin")
def disable_user(user_id: int):
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    user.estado = "Inactivo"
    log_event(
        "desactivacion_usuario",
        "usuario",
        "exitoso",
        entity_id=user.id,
        detail={"target_user_nombre": user.nombre},
    )
    db.session.commit()
    return jsonify(_user_payload(user))


@api_bp.get("/areas")
@require_auth()
def list_areas():
    items = Area.query.order_by(Area.nombre).all()
    return jsonify(
        {"items": [{"id": item.id, "nombre": item.nombre, "descripcion": item.descripcion} for item in items]}
    )


@api_bp.post("/areas")
@require_roles("Admin")
def create_area():
    payload = request.get_json(silent=True) or {}
    if not payload.get("nombre"):
        raise ValidationError("nombre es obligatorio.")
    area = Area(nombre=payload["nombre"].strip(), descripcion=payload.get("descripcion"))
    db.session.add(area)
    db.session.flush()
    log_event(
        "creacion_area",
        "area",
        "exitoso",
        entity_id=area.id,
        detail={"area_nombre": area.nombre},
    )
    db.session.commit()
    return jsonify({"id": area.id, "nombre": area.nombre, "descripcion": area.descripcion}), 201


@api_bp.patch("/areas/<int:area_id>")
@require_roles("Admin")
def update_area(area_id: int):
    area = Area.query.get(area_id)
    if not area:
        raise NotFoundError("Area no encontrada.")
    payload = request.get_json(silent=True) or {}
    if "nombre" in payload:
        area.nombre = payload["nombre"].strip()
    if "descripcion" in payload:
        area.descripcion = payload["descripcion"]
    log_event(
        "edicion_area",
        "area",
        "exitoso",
        entity_id=area.id,
        detail={"area_nombre": area.nombre},
    )
    db.session.commit()
    return jsonify({"id": area.id, "nombre": area.nombre, "descripcion": area.descripcion})


@api_bp.get("/zonas")
@require_auth()
def list_zones():
    zones = ZonaReunion.query.order_by(ZonaReunion.nombre).all()
    return jsonify({"items": [_zone_payload(zone) for zone in zones]})


@api_bp.post("/zonas")
@require_roles("Admin")
def create_zone():
    payload = request.get_json(silent=True) or {}
    required = ("nombre", "ubicacion", "capacidad")
    if any(not payload.get(field) for field in required):
        raise ValidationError("nombre, ubicacion y capacidad son obligatorios.")
    zone = ZonaReunion(
        nombre=payload["nombre"].strip(),
        ubicacion=payload["ubicacion"].strip(),
        capacidad=int(payload["capacidad"]),
        area_id=int(payload["area_id"]) if payload.get("area_id") else None,
        estado=payload.get("estado", "Activa"),
        margen_operativo_minutos=int(payload.get("margen_operativo_minutos", 5)),
        descripcion=payload.get("descripcion"),
    )
    if zone.area_id and not Area.query.get(zone.area_id):
        raise ValidationError("Area invalida para la zona.")
    db.session.add(zone)
    db.session.flush()
    log_event(
        "creacion_zona",
        "zona",
        "exitoso",
        entity_id=zone.id,
        detail={"zona_nombre": zone.nombre, "capacidad": zone.capacidad},
    )
    db.session.commit()
    return jsonify(_zone_payload(zone)), 201


@api_bp.patch("/zonas/<int:zone_id>")
@require_roles("Admin")
def update_zone(zone_id: int):
    zone = ZonaReunion.query.get(zone_id)
    if not zone:
        raise NotFoundError("Zona no encontrada.")
    payload = request.get_json(silent=True) or {}
    for field in ("nombre", "ubicacion", "descripcion", "estado"):
        if field in payload:
            setattr(zone, field, payload[field].strip() if isinstance(payload[field], str) else payload[field])
    if "capacidad" in payload:
        zone.capacidad = int(payload["capacidad"])
    if "area_id" in payload:
        zone.area_id = int(payload["area_id"]) if payload["area_id"] else None
        if zone.area_id and not Area.query.get(zone.area_id):
            raise ValidationError("Area invalida para la zona.")
    if "margen_operativo_minutos" in payload:
        zone.margen_operativo_minutos = int(payload["margen_operativo_minutos"])
    log_event(
        "edicion_zona",
        "zona",
        "exitoso",
        entity_id=zone.id,
        detail={"zona_nombre": zone.nombre},
    )
    db.session.commit()
    return jsonify(_zone_payload(zone))


@api_bp.get("/reuniones")
@require_auth()
def list_meetings():
    actor = g.current_user
    query = Reunion.query.order_by(Reunion.fecha, Reunion.hora_inicio)
    if actor.role.nombre == "Admin":
        items = query.all()
    elif actor.role.nombre == "Agendador":
        items = query.filter(
            (Reunion.creador_id == actor.id)
            | Reunion.participantes.any(usuario_id=actor.id)
        ).all()
    else:
        items = query.filter(Reunion.participantes.any(usuario_id=actor.id)).all()
    return jsonify({"items": [serialize_meeting(item) for item in items]})


@api_bp.get("/reuniones/<int:meeting_id>")
@require_auth()
def get_meeting(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    return jsonify(serialize_meeting(meeting))


@api_bp.post("/reuniones")
@require_roles("Admin", "Agendador")
def create_meeting_route():
    payload = request.get_json(silent=True) or {}
    meeting = create_meeting(payload)
    return jsonify(serialize_meeting(meeting)), 201


@api_bp.patch("/reuniones/<int:meeting_id>")
@require_roles("Admin")
def update_meeting_route(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    updated = update_meeting(meeting, request.get_json(silent=True) or {})
    return jsonify(serialize_meeting(updated))


@api_bp.post("/reuniones/<int:meeting_id>/cancelar")
@require_roles("Admin")
def cancel_meeting_route(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    canceled = cancel_meeting(meeting)
    return jsonify(serialize_meeting(canceled))


@api_bp.post("/reuniones/<int:meeting_id>/aceptar")
@require_auth()
def accept_meeting_route(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    respond_to_meeting(meeting, accept=True)
    return jsonify(serialize_meeting(meeting))


@api_bp.post("/reuniones/<int:meeting_id>/rechazar")
@require_auth()
def reject_meeting_route(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    payload = request.get_json(silent=True) or {}
    respond_to_meeting(meeting, accept=False, reason=payload.get("razon"))
    return jsonify(serialize_meeting(meeting))


@api_bp.get("/logs")
@require_roles("Admin")
def list_logs():
    logs = LogSistema.query.order_by(LogSistema.fecha_hora.desc()).limit(200).all()
    return jsonify(
        {
            "items": [
                {
                    "id": log.id,
                    "usuario_actor_id": log.usuario_actor_id,
                    "usuario_actor_nombre": log.usuario_actor.nombre if log.usuario_actor else None,
                    "rol_actor": log.rol_actor,
                    "accion": log.accion,
                    "entidad": log.entidad,
                    "entidad_id": log.entidad_id,
                    "resultado": log.resultado,
                    "descripcion_humana": log.descripcion_humana,
                    "detalle_seguro": log.detalle_seguro,
                    "ip": log.ip,
                    "user_agent": log.user_agent,
                    "fecha_hora": log.fecha_hora.isoformat(),
                }
                for log in logs
            ]
        }
    )


@api_bp.get("/configuracion")
@require_roles("Admin")
def list_config():
    items = Configuracion.query.order_by(Configuracion.clave).all()
    return jsonify({"items": [{"clave": item.clave, "valor": item.valor} for item in items]})


@api_bp.patch("/configuracion")
@require_roles("Admin")
def update_config():
    payload = request.get_json(silent=True) or {}
    for key, value in payload.items():
        item = Configuracion.query.filter_by(clave=key).first()
        if item:
            item.valor = str(value)
    log_event("edicion_configuracion", "configuracion", "exitoso")
    db.session.commit()
    return jsonify({"message": "Configuracion actualizada."})
