from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, make_response, redirect, request, url_for

from app.audit import log_event
from app.auth import clear_session_cookies, require_auth, require_roles, set_session_cookies
from app.constants import OPERATOR_ROLES, ROLE_ADMIN, ROLE_COLABORADOR, ROLE_SECRETARIA
from app.errors import AuthenticationError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import (
    Area,
    Configuracion,
    LogSistema,
    Reunion,
    ReunionHistorial,
    ReunionParticipante,
    ReunionSolicitud,
    Role,
    Usuario,
    ZonaReunion,
)
from app.permissions import ensure_meeting_access
from app.security import hash_password, issue_session, verify_password
from app.services.meetings import (
    cancel_meeting,
    create_meeting,
    respond_to_meeting,
    serialize_meeting,
    update_meeting,
)
from app.services.internal_meetings import create_internal_area_meeting
from app.services.notifications import register_device_token


api_bp = Blueprint("api", __name__, url_prefix="/api")


def _user_payload(user: Usuario) -> dict:
    return {
        "id": user.id,
        "nombre": user.nombre,
        "correo": user.correo,
        "telefono": user.telefono,
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


def _mobile_user_payload(user: Usuario) -> dict:
    return {
        "id": user.id,
        "nombre": user.nombre,
        "correo": user.correo,
        "estado": user.estado,
        "role": user.role.nombre,
        "area": {"id": user.area.id, "nombre": user.area.nombre},
    }


def _mobile_zone_payload(zone: ZonaReunion) -> dict:
    return {
        "id": zone.id,
        "nombre": zone.nombre,
        "ubicacion": zone.ubicacion,
        "capacidad": zone.capacidad,
    }


def _meeting_history_payload(row: ReunionHistorial) -> dict:
    return {
        "id": row.id,
        "reunion_id": row.reunion_id,
        "actor_usuario_id": row.actor_usuario_id,
        "actor_nombre": row.actor.nombre if row.actor else None,
        "tipo_evento": row.tipo_evento,
        "estado_anterior": row.estado_anterior,
        "estado_nuevo": row.estado_nuevo,
        "snapshot_json": row.snapshot_json,
        "changed_at": row.changed_at.isoformat(),
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
        "responsable": {
            "id": meeting.responsable.id,
            "nombre": meeting.responsable.nombre,
            "correo": meeting.responsable.correo,
        },
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


def _mobile_visible_meetings(actor: Usuario) -> list[Reunion]:
    if actor.role.nombre in OPERATOR_ROLES:
        return Reunion.query.order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc()).all()
    return (
        Reunion.query.filter(Reunion.participantes.any(usuario_id=actor.id))
        .order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc())
        .all()
    )


def _mobile_request_payload(solicitud: ReunionSolicitud) -> dict:
    return {
        "id": solicitud.id,
        "titulo": solicitud.titulo,
        "motivo": solicitud.motivo,
        "fecha": solicitud.fecha.isoformat(),
        "hora_inicio": solicitud.hora_inicio.strftime("%H:%M"),
        "hora_fin": solicitud.hora_fin.strftime("%H:%M"),
        "estado": solicitud.estado,
        "prioridad": solicitud.prioridad,
        "observacion_solicitante": solicitud.observacion_solicitante,
        "respuesta_secretaria": solicitud.respuesta_secretaria,
        "reunion_id": solicitud.reunion_id,
        "solicitante": _mobile_user_payload(solicitud.solicitante),
        "zona": _mobile_zone_payload(solicitud.zona),
        "participantes": [_mobile_user_payload(item.usuario) for item in solicitud.participantes],
        "created_at": solicitud.created_at.isoformat(),
        "updated_at": solicitud.updated_at.isoformat(),
    }


def _mobile_visible_requests(actor: Usuario) -> list[ReunionSolicitud]:
    query = ReunionSolicitud.query.order_by(ReunionSolicitud.created_at.desc())
    if actor.role.nombre in (ROLE_ADMIN, ROLE_SECRETARIA):
        return query.all()
    return query.filter_by(solicitante_usuario_id=actor.id).all()


def _parse_availability_args() -> tuple[date, list[int]]:
    raw_fecha = (request.args.get("fecha") or "").strip()
    if not raw_fecha:
        raise ValidationError("fecha es obligatoria.")
    try:
        fecha = date.fromisoformat(raw_fecha)
    except ValueError as exc:
        raise ValidationError("fecha debe tener formato YYYY-MM-DD.") from exc

    raw_ids = (request.args.get("usuario_ids") or "").strip()
    if not raw_ids:
        raise ValidationError("usuario_ids es obligatorio.")
    try:
        user_ids = [int(value.strip()) for value in raw_ids.split(",") if value.strip()]
    except ValueError as exc:
        raise ValidationError("usuario_ids debe ser una lista de enteros separados por comas.") from exc
    if not user_ids:
        raise ValidationError("usuario_ids es obligatorio.")
    return fecha, list(dict.fromkeys(user_ids))


def _participant_block_status(response_status: str) -> str:
    if response_status == "Rechazada":
        return "rechazado"
    if response_status == "Pendiente":
        return "pendiente"
    return "ocupado"


def _daily_user_status(blocks: list[dict]) -> str:
    blocking = [item for item in blocks if item["estado"] in ("ocupado", "pendiente")]
    if not blocking:
        return "disponible"
    occupied_minutes = 0
    for item in blocking:
        start = datetime.strptime(item["inicio"], "%H:%M")
        end = datetime.strptime(item["fin"], "%H:%M")
        occupied_minutes += int((end - start).total_seconds() // 60)
    work_start = datetime.strptime(
        (Configuracion.query.filter_by(clave="horario_laboral_inicio").first() or Configuracion(valor="08:00")).valor,
        "%H:%M",
    )
    work_end = datetime.strptime(
        (Configuracion.query.filter_by(clave="horario_laboral_fin").first() or Configuracion(valor="17:00")).valor,
        "%H:%M",
    )
    workday_minutes = int((work_end - work_start).total_seconds() // 60)
    if workday_minutes > 0 and occupied_minutes >= workday_minutes:
        return "ocupado_total"
    return "ocupado_parcial"


def _availability_payload(actor: Usuario) -> dict:
    fecha, requested_ids = _parse_availability_args()
    users = Usuario.query.filter(Usuario.id.in_(requested_ids)).order_by(Usuario.nombre).all()
    found_ids = {user.id for user in users}
    missing_ids = [user_id for user_id in requested_ids if user_id not in found_ids]

    if actor.role.nombre not in (ROLE_ADMIN, ROLE_SECRETARIA):
        forbidden_users = [user for user in users if user.area_id != actor.area_id]
        if forbidden_users:
            raise ForbiddenError("No tiene permiso para consultar disponibilidad de usuarios de otra área.")

    participant_rows = (
        db.session.query(ReunionParticipante)
        .join(Reunion, Reunion.id == ReunionParticipante.reunion_id)
        .filter(
            ReunionParticipante.usuario_id.in_(found_ids),
            Reunion.fecha == fecha,
            Reunion.estado != "Cancelada",
        )
        .order_by(Reunion.hora_inicio.asc(), Reunion.hora_fin.asc())
        .all()
    )
    blocks_by_user: dict[int, list[dict]] = {user.id: [] for user in users}
    for row in participant_rows:
        meeting = row.reunion
        blocks_by_user.setdefault(row.usuario_id, []).append(
            {
                "reunion_id": meeting.id,
                "titulo": meeting.titulo,
                "inicio": meeting.hora_inicio.strftime("%H:%M"),
                "fin": meeting.hora_fin.strftime("%H:%M"),
                "estado": _participant_block_status(row.estado_respuesta),
                "tipo": "reunion",
                "prioridad": meeting.prioridad,
            }
        )

    return {
        "fecha": fecha.isoformat(),
        "usuarios_no_encontrados": missing_ids,
        "usuarios": [
            {
                "id": user.id,
                "nombre": user.nombre,
                "correo": user.correo,
                "area": {"id": user.area.id, "nombre": user.area.nombre},
                "reuniones_dia": len(blocks_by_user.get(user.id, [])),
                "estado_dia": _daily_user_status(blocks_by_user.get(user.id, [])),
                "bloques": blocks_by_user.get(user.id, []),
            }
            for user in users
        ],
    }


def _request_payload() -> dict:
    if request.form:
        return {
            key: request.form.getlist(key) if key == "participant_ids" else request.form.get(key)
            for key in request.form
            if key != "csrf_token"
        }
    return request.get_json(silent=True) or {}


def _friendly_internal_meeting_error(message: str) -> str:
    lowered = message.lower()
    if "aprobacion" in lowered or "aprobación" in lowered or "solicitud" in lowered:
        return "Esta reunión requiere aprobación de Secretaría. Cree una solicitud institucional."
    return message


def _get_login_user(payload: dict, channel: str) -> Usuario:
    correo = (payload.get("correo") or "").strip().lower()
    password = payload.get("password") or ""
    if not correo or not password:
        raise ValidationError("correo y password son obligatorios.")
    user = Usuario.query.filter_by(correo=correo).first()
    max_attempts = int(
        (Configuracion.query.filter_by(clave="max_intentos_login").first() or Configuracion(valor="5")).valor
    )
    if not user:
        log_event("login_fallido", channel, "rechazado", detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    if user.estado != "Activo":
        log_event("login_fallido", channel, "rechazado", entity_id=user.id, detail={"motivo": "usuario_inactivo"})
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
        log_event("login_fallido", channel, "rechazado", entity_id=user.id, detail={"correo": correo})
        db.session.commit()
        raise AuthenticationError("Credenciales invalidas.")
    user.failed_login_attempts = 0
    user.locked_until = None
    user.ultimo_login_at = datetime.utcnow()
    return user


@api_bp.post("/auth/login")
def login():
    user = _get_login_user(request.get_json(silent=True) or {}, "auth")
    session_token, csrf_token, session = issue_session(user)
    log_event("login", "auth", "exitoso", entity_id=user.id)
    db.session.commit()
    response = make_response(
        jsonify({"message": "Login exitoso.", "csrf_token": csrf_token, "user": _user_payload(user)})
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


@api_bp.post("/mobile/auth/login")
def mobile_login():
    user = _get_login_user(request.get_json(silent=True) or {}, "auth_mobile")
    access_token, csrf_token, session = issue_session(user)
    log_event("login", "auth_mobile", "exitoso", entity_id=user.id)
    db.session.commit()
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in_minutes": current_app.config["SESSION_TTL_MINUTES"],
            "csrf_token": csrf_token,
            "user": _mobile_user_payload(user),
        }
    )


@api_bp.get("/mobile/auth/me")
@require_auth()
def mobile_me():
    return jsonify({"user": _mobile_user_payload(g.current_user)})


@api_bp.post("/mobile/auth/logout")
@require_auth()
def mobile_logout():
    g.current_session.activa = False
    log_event("logout", "auth_mobile", "exitoso", entity_id=g.current_user.id)
    db.session.commit()
    return jsonify({"message": "Sesion cerrada."})


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
    role_name = g.current_user.role.nombre
    if role_name not in (ROLE_ADMIN, ROLE_SECRETARIA):
        raise ForbiddenError("No tiene permiso para listar usuarios.")
    users = Usuario.query.order_by(Usuario.id).all()
    return jsonify({"items": [_user_payload(item) for item in users]})


@api_bp.get("/usuarios/buscar")
@require_auth()
def search_users():
    actor = g.current_user
    if actor.role.nombre not in (ROLE_ADMIN, ROLE_SECRETARIA):
        raise ForbiddenError("No tiene permiso para buscar usuarios.")
    q = (request.args.get("q") or "").strip().lower()
    area_id_raw = request.args.get("area_id")
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


@api_bp.post("/usuarios")
@require_roles(ROLE_ADMIN)
def create_user():
    payload = request.get_json(silent=True) or {}
    required = ("nombre", "correo", "password", "role_id", "area_id")
    if any(not payload.get(field) for field in required):
        raise ValidationError("nombre, correo, password, role_id y area_id son obligatorios.")
    if Usuario.query.filter_by(correo=payload["correo"].strip().lower()).first():
        raise ValidationError("El correo ya existe.")
    role_id = int(payload["role_id"])
    area_id = int(payload["area_id"])
    role = Role.query.get(role_id)
    area = Area.query.get(area_id)
    if not role:
        raise ValidationError("Rol invalido.")
    if not area:
        raise ValidationError("Area invalida.")
    user = Usuario(
        nombre=payload["nombre"].strip(),
        correo=payload["correo"].strip().lower(),
        telefono=(payload.get("telefono") or "").strip() or None,
        password_hash=hash_password(payload["password"]),
        role_id=role_id,
        area_id=area_id,
        estado=payload.get("estado", "Activo"),
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
            "area_nombre": area.nombre,
            "role_nombre": role.nombre,
        },
    )
    db.session.commit()
    return jsonify(_user_payload(user)), 201


@api_bp.patch("/usuarios/<int:user_id>")
@require_roles(ROLE_ADMIN)
def update_user(user_id: int):
    payload = request.get_json(silent=True) or {}
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    if "nombre" in payload:
        user.nombre = payload["nombre"].strip()
    if "telefono" in payload:
        user.telefono = (payload["telefono"] or "").strip() or None
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
@require_roles(ROLE_ADMIN)
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
    return jsonify({"items": [{"id": item.id, "nombre": item.nombre, "descripcion": item.descripcion} for item in items]})


@api_bp.post("/areas")
@require_roles(ROLE_ADMIN)
def create_area():
    payload = request.get_json(silent=True) or {}
    if not payload.get("nombre"):
        raise ValidationError("nombre es obligatorio.")
    area = Area(
        nombre=payload["nombre"].strip(),
        descripcion=payload.get("descripcion"),
        estado=payload.get("estado", "Activa"),
    )
    db.session.add(area)
    db.session.flush()
    log_event("creacion_area", "area", "exitoso", entity_id=area.id, detail={"area_nombre": area.nombre})
    db.session.commit()
    return jsonify({"id": area.id, "nombre": area.nombre, "descripcion": area.descripcion}), 201


@api_bp.patch("/areas/<int:area_id>")
@require_roles(ROLE_ADMIN)
def update_area(area_id: int):
    area = Area.query.get(area_id)
    if not area:
        raise NotFoundError("Area no encontrada.")
    payload = request.get_json(silent=True) or {}
    if "nombre" in payload:
        area.nombre = payload["nombre"].strip()
    if "descripcion" in payload:
        area.descripcion = payload["descripcion"]
    if "estado" in payload:
        area.estado = payload["estado"]
    log_event("edicion_area", "area", "exitoso", entity_id=area.id, detail={"area_nombre": area.nombre})
    db.session.commit()
    return jsonify({"id": area.id, "nombre": area.nombre, "descripcion": area.descripcion, "estado": area.estado})


@api_bp.get("/zonas")
@require_auth()
def list_zones():
    zones = ZonaReunion.query.order_by(ZonaReunion.nombre).all()
    return jsonify({"items": [_zone_payload(zone) for zone in zones]})


@api_bp.get("/mobile/zonas")
@require_auth()
def mobile_zones():
    zones = ZonaReunion.query.filter_by(estado="Activa").order_by(ZonaReunion.nombre).all()
    return jsonify({"items": [_mobile_zone_payload(zone) for zone in zones]})


@api_bp.get("/mobile/usuarios/buscar")
@require_auth()
def mobile_search_users():
    q = (request.args.get("q") or "").strip().lower()
    area_id_raw = request.args.get("area_id")
    area_id = int(area_id_raw) if area_id_raw else None
    query = Usuario.query.filter_by(estado="Activo")
    if area_id:
        query = query.filter_by(area_id=area_id)
    if q:
        like = f"%{q}%"
        query = query.filter((Usuario.nombre.ilike(like)) | (Usuario.correo.ilike(like)))
    users = query.order_by(Usuario.nombre).limit(20).all()
    return jsonify({"items": [_mobile_user_payload(user) for user in users]})


@api_bp.get("/disponibilidad/usuarios")
@require_auth()
def user_availability():
    return jsonify(_availability_payload(g.current_user))


@api_bp.get("/mobile/disponibilidad/usuarios")
@require_auth()
def mobile_user_availability():
    return jsonify(_availability_payload(g.current_user))


@api_bp.post("/zonas")
@require_roles(ROLE_ADMIN)
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
@require_roles(ROLE_ADMIN)
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
    log_event("edicion_zona", "zona", "exitoso", entity_id=zone.id, detail={"zona_nombre": zone.nombre})
    db.session.commit()
    return jsonify(_zone_payload(zone))


@api_bp.get("/reuniones")
@require_auth()
def list_meetings():
    actor = g.current_user
    query = Reunion.query.order_by(Reunion.fecha, Reunion.hora_inicio)
    if actor.role.nombre in OPERATOR_ROLES:
        items = query.all()
    else:
        items = query.filter(Reunion.participantes.any(usuario_id=actor.id)).all()
    return jsonify({"items": [serialize_meeting(item) for item in items]})


@api_bp.get("/reuniones/<int:meeting_id>")
@require_auth()
def get_meeting(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    return jsonify(serialize_meeting(meeting))


@api_bp.get("/reuniones/<int:meeting_id>/historial")
@require_auth()
def get_meeting_history(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    ensure_meeting_access(meeting)
    rows = ReunionHistorial.query.filter_by(reunion_id=meeting_id).order_by(ReunionHistorial.changed_at.desc()).all()
    return jsonify({"items": [_meeting_history_payload(row) for row in rows]})


@api_bp.post("/reuniones")
@require_roles(*OPERATOR_ROLES)
def create_meeting_route():
    meeting = create_meeting(request.get_json(silent=True) or {})
    return jsonify(serialize_meeting(meeting)), 201


@api_bp.post("/reuniones-internas")
@require_auth()
def create_internal_meeting_route():
    try:
        meeting = create_internal_area_meeting(g.current_user, _request_payload(), "web")
    except (ValidationError, ConflictError, ForbiddenError) as exc:
        if request.form:
            return redirect(
                url_for(
                    "web.internal_meetings_new",
                    error=_friendly_internal_meeting_error(exc.message),
                )
            )
        raise
    if request.form:
        return redirect(
            url_for(
                "web.admin_meeting_detail",
                meeting_id=meeting.id,
                success="Reunión interna creada correctamente.",
            )
        )
    return jsonify(serialize_meeting(meeting)), 201


@api_bp.patch("/reuniones/<int:meeting_id>")
@require_roles(*OPERATOR_ROLES)
def update_meeting_route(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    updated = update_meeting(meeting, request.get_json(silent=True) or {})
    return jsonify(serialize_meeting(updated))


@api_bp.post("/reuniones/<int:meeting_id>/cancelar")
@require_roles(*OPERATOR_ROLES)
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
    respond_to_meeting(meeting, accept=False, reason=(request.get_json(silent=True) or {}).get("razon"))
    return jsonify(serialize_meeting(meeting))


@api_bp.get("/mobile/reuniones")
@require_auth()
def mobile_meetings():
    actor = g.current_user
    meetings = _mobile_visible_meetings(actor)
    return jsonify({"items": [_mobile_meeting_payload(meeting, actor) for meeting in meetings]})


@api_bp.post("/mobile/reuniones-internas")
@require_auth()
def mobile_create_internal_meeting():
    meeting = create_internal_area_meeting(
        g.current_user,
        request.get_json(silent=True) or {},
        "mobile",
    )
    return jsonify(_mobile_meeting_payload(meeting, g.current_user)), 201


@api_bp.get("/mobile/sync")
@require_auth()
def mobile_sync():
    actor = g.current_user
    meetings = _mobile_visible_meetings(actor)
    solicitudes = _mobile_visible_requests(actor)
    return jsonify(
        {
            "reuniones": [_mobile_meeting_payload(meeting, actor) for meeting in meetings],
            "solicitudes": [_mobile_request_payload(solicitud) for solicitud in solicitudes],
            "server_time": datetime.utcnow().isoformat() + "Z",
        }
    )


@api_bp.get("/mobile/solicitudes")
@require_auth()
def mobile_requests():
    solicitudes = _mobile_visible_requests(g.current_user)
    return jsonify({"items": [_mobile_request_payload(solicitud) for solicitud in solicitudes]})


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


@api_bp.get("/logs")
@require_roles(ROLE_ADMIN)
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
@require_roles(ROLE_ADMIN)
def list_config():
    items = Configuracion.query.order_by(Configuracion.clave).all()
    return jsonify({"items": [{"clave": item.clave, "valor": item.valor} for item in items]})


@api_bp.patch("/configuracion")
@require_roles(ROLE_ADMIN)
def update_config():
    payload = request.get_json(silent=True) or {}
    for key, value in payload.items():
        item = Configuracion.query.filter_by(clave=key).first()
        if item:
            item.valor = str(value)
    log_event("edicion_configuracion", "configuracion", "exitoso")
    db.session.commit()
    return jsonify({"message": "Configuracion actualizada."})
