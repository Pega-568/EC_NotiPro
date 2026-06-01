from __future__ import annotations

from datetime import date, datetime, timedelta
from calendar import monthcalendar

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for

from app.audit import log_event
from app.auth import clear_session_cookies, require_auth, require_roles, set_session_cookies
from app.constants import OPERATOR_ROLES, ROLE_ADMIN, ROLE_COLABORADOR, ROLE_SECRETARIA
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Area, Configuracion, LogSistema, Reunion, Role, Usuario, ZonaReunion
from app.security import hash_password, issue_session, verify_password
from app.services.meetings import cancel_meeting, create_meeting, serialize_meeting, update_meeting


web_bp = Blueprint("web", __name__)


def _admin_base_context() -> dict:
    return {
        "roles": Role.query.order_by(Role.nombre).all(),
        "areas": Area.query.order_by(Area.nombre).all(),
        "zones": ZonaReunion.query.order_by(ZonaReunion.nombre).all(),
        "users": Usuario.query.order_by(Usuario.nombre).all(),
    }


def _redirect_with_message(endpoint: str, *, success: str | None = None, error: str | None = None, **values):
    params = {}
    if success:
        params["success"] = success
    if error:
        params["error"] = error
    params.update(values)
    return redirect(url_for(endpoint, **params))


def _request_messages() -> tuple[str | None, str | None]:
    return request.args.get("success"), request.args.get("error")


def _user_form_payload(existing: Usuario | None = None) -> dict:
    return {
        "nombre": request.form.get("nombre", getattr(existing, "nombre", "")).strip(),
        "correo": request.form.get("correo", getattr(existing, "correo", "")).strip().lower(),
        "telefono": request.form.get("telefono", getattr(existing, "telefono", "") or "").strip() or None,
        "role_id": request.form.get("role_id", str(getattr(existing, "role_id", "") or "")),
        "area_id": request.form.get("area_id", str(getattr(existing, "area_id", "") or "")),
        "estado": request.form.get("estado", getattr(existing, "estado", "Activo")),
        "password_temporal": request.form.get("password_temporal", "").strip(),
    }


def _validate_user_form(existing: Usuario | None = None) -> tuple[dict, Role, Area]:
    payload = _user_form_payload(existing)
    if not payload["nombre"] or not payload["correo"] or not payload["role_id"] or not payload["area_id"]:
        raise ValidationError("Nombre, correo, rol y area son obligatorios.")
    role = Role.query.get(int(payload["role_id"]))
    area = Area.query.get(int(payload["area_id"]))
    if not role:
        raise ValidationError("Rol invalido.")
    if not area:
        raise ValidationError("Area invalida.")
    if area.estado != "Activa":
        raise ValidationError("El area asignada debe estar activa.")
    duplicate = Usuario.query.filter_by(correo=payload["correo"]).first()
    if duplicate and (not existing or duplicate.id != existing.id):
        raise ValidationError("El correo ya existe.")
    return payload, role, area


def _area_form_payload(existing: Area | None = None) -> dict:
    return {
        "nombre": request.form.get("nombre", getattr(existing, "nombre", "")).strip(),
        "descripcion": request.form.get("descripcion", getattr(existing, "descripcion", "") or "").strip() or None,
        "estado": request.form.get("estado", getattr(existing, "estado", "Activa")),
    }


def _zone_form_payload(existing: ZonaReunion | None = None) -> dict:
    return {
        "nombre": request.form.get("nombre", getattr(existing, "nombre", "")).strip(),
        "ubicacion": request.form.get("ubicacion", getattr(existing, "ubicacion", "")).strip(),
        "capacidad": request.form.get("capacidad", str(getattr(existing, "capacidad", "") or "")),
        "area_id": request.form.get("area_id", str(getattr(existing, "area_id", "") or "")),
        "estado": request.form.get("estado", getattr(existing, "estado", "Activa")),
        "margen_operativo_minutos": request.form.get(
            "margen_operativo_minutos", str(getattr(existing, "margen_operativo_minutos", 5))
        ),
        "descripcion": request.form.get("descripcion", getattr(existing, "descripcion", "") or "").strip() or None,
    }


def _meeting_form_payload(existing: Reunion | None = None) -> dict:
    participant_ids = request.form.getlist("participant_ids")
    return {
        "titulo": request.form.get("titulo", getattr(existing, "titulo", "")).strip(),
        "motivo": request.form.get("motivo", getattr(existing, "motivo", "")).strip(),
        "fecha": request.form.get(
            "fecha",
            request.args.get("fecha", existing.fecha.isoformat() if existing and existing.fecha else (date.today() + timedelta(days=1)).isoformat()),
        ),
        "hora_inicio": request.form.get(
            "hora_inicio",
            request.args.get("hora_inicio", existing.hora_inicio.strftime("%H:%M") if existing and existing.hora_inicio else "09:00"),
        ),
        "hora_fin": request.form.get(
            "hora_fin",
            request.args.get("hora_fin", existing.hora_fin.strftime("%H:%M") if existing and existing.hora_fin else "10:00"),
        ),
        "zona_id": request.form.get("zona_id", request.args.get("zona_id", str(getattr(existing, "zona_id", "") or ""))),
        "responsable_reunion_id": request.form.get(
            "responsable_reunion_id",
            request.args.get(
                "responsable_reunion_id",
                str(getattr(existing, "responsable_reunion_id", "") or ""),
            ),
        ),
        "prioridad": request.form.get("prioridad", getattr(existing, "prioridad", "Media")),
        "participant_ids": participant_ids,
    }


def _config_map() -> dict[str, Configuracion]:
    return {item.clave: item for item in Configuracion.query.order_by(Configuracion.clave).all()}


def _selected_participant_cards(participant_ids: list[str]) -> list[dict]:
    if not participant_ids:
        return []
    ids = [int(value) for value in participant_ids]
    users = Usuario.query.filter(Usuario.id.in_(ids)).all()
    by_id = {user.id: user for user in users}
    cards = []
    for user_id in ids:
        user = by_id.get(user_id)
        if user:
            cards.append(
                {
                    "id": user.id,
                    "nombre": user.nombre,
                    "correo": user.correo,
                    "area": user.area.nombre,
                }
            )
    return cards


def _responsable_candidates():
    return Usuario.query.filter_by(estado="Activo").order_by(Usuario.nombre).all()


def _bool_config(key: str, default: bool = False) -> bool:
    item = Configuracion.query.filter_by(clave=key).first()
    if not item:
        return default
    return item.valor.lower() == "true"


def _calendar_scope(view_mode: str, anchor: date) -> tuple[date, date]:
    if view_mode == "day":
        return anchor, anchor
    if view_mode == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if view_mode in ("month", "area", "zone", "list"):
        start = anchor.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    return date.min, date.max


def _meeting_rows_for_calendar(meetings: list[Reunion]) -> list[dict]:
    rows = []
    for meeting in meetings:
        data = serialize_meeting(meeting)
        rows.append(
            {
                "meeting": meeting,
                "data": data,
                "response_label": f"{data['resumen_respuestas']['aceptadas']}/{data['resumen_respuestas']['total']} aceptadas",
            }
        )
    return rows


@web_bp.get("/favicon.ico")
def favicon():
    return ("", 204)


@web_bp.get("/")
def home():
    if g.current_user:
        if g.current_user.role.nombre == ROLE_ADMIN:
            return redirect(url_for("web.admin_dashboard"))
        if g.current_user.role.nombre == ROLE_SECRETARIA:
            return redirect(url_for("web.scheduler_dashboard"))
        return redirect(url_for("web.user_dashboard"))
    return redirect(url_for("web.login"))


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")
        user = Usuario.query.filter_by(correo=correo).first()
        max_attempts = int(
            (Configuracion.query.filter_by(clave="max_intentos_login").first() or Configuracion(valor="5")).valor
        )
        if not user:
            log_event("login_fallido", "auth_web", "rechazado", detail={"correo": correo})
            db.session.commit()
            error = "Credenciales invalidas."
            return render_template("auth/login.html", error=error)
        if user.estado != "Activo":
            log_event("login_fallido", "auth_web", "rechazado", entity_id=user.id, detail={"motivo": "usuario_inactivo"})
            db.session.commit()
            error = "Usuario inactivo."
            return render_template("auth/login.html", error=error)
        if user.locked_until and user.locked_until > datetime.utcnow():
            error = "Usuario bloqueado temporalmente."
            return render_template("auth/login.html", error=error)
        if verify_password(user.password_hash, password):
            user.failed_login_attempts = 0
            user.locked_until = None
            token, csrf_token, session = issue_session(user)
            user.ultimo_login_at = datetime.utcnow()
            log_event("login", "auth_web", "exitoso", entity_id=user.id)
            db.session.commit()
            response = make_response(redirect(url_for("web.home")))
            return set_session_cookies(response, token, csrf_token)
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.utcnow().replace(microsecond=0) + timedelta(
                minutes=current_app.config["LOGIN_LOCK_MINUTES"]
            )
        log_event("login_fallido", "auth_web", "rechazado", entity_id=user.id, detail={"correo": correo})
        db.session.commit()
        error = "Credenciales invalidas."
    return render_template("auth/login.html", error=error)


@web_bp.post("/logout")
@require_auth(api=False)
def logout():
    g.current_session.activa = False
    log_event("logout", "auth_web", "exitoso", entity_id=g.current_user.id)
    db.session.commit()
    response = make_response(redirect(url_for("web.login")))
    return clear_session_cookies(response)


@web_bp.get("/admin")
def admin_redirect():
    return redirect(url_for("web.admin_dashboard"))


@web_bp.get("/web/admin")
@require_roles(ROLE_ADMIN, api=False)
def admin_dashboard():
    success, error = _request_messages()
    today = date.today()
    meetings_today = Reunion.query.filter_by(fecha=today).all()
    pending_responses = sum(
        1
        for meeting in Reunion.query.all()
        for participant in meeting.participantes
        if participant.estado_respuesta == "Pendiente" and meeting.estado != "Cancelada"
    )
    rejected_responses = sum(
        1
        for meeting in Reunion.query.all()
        for participant in meeting.participantes
        if participant.estado_respuesta == "Rechazada"
    )
    occupied_zones = len({meeting.zona_id for meeting in meetings_today if meeting.estado != "Cancelada"})
    counts = {
        "usuarios": Usuario.query.count(),
        "areas": Area.query.count(),
        "zonas": ZonaReunion.query.count(),
        "reuniones": Reunion.query.count(),
        "reuniones_hoy": len(meetings_today),
        "pendientes_respuesta": pending_responses,
        "rechazos": rejected_responses,
        "zonas_ocupadas_hoy": occupied_zones,
    }
    upcoming_meetings = Reunion.query.order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc()).limit(8).all()
    return render_template(
        "admin/dashboard.html",
        counts=counts,
        meetings=upcoming_meetings,
        serialize_meeting=serialize_meeting,
        debug_mode=_bool_config("debug_mode", False),
        success=success,
        error=error,
    )


@web_bp.get("/web/admin/calendario")
@require_roles(*OPERATOR_ROLES, api=False)
def admin_calendar():
    success, error = _request_messages()
    view_mode = request.args.get("view", "month")
    anchor_raw = request.args.get("date")
    anchor = date.fromisoformat(anchor_raw) if anchor_raw else date.today()
    area_id = int(request.args["area_id"]) if request.args.get("area_id") else None
    zone_id = int(request.args["zone_id"]) if request.args.get("zone_id") else None
    start_date, end_date = _calendar_scope(view_mode, anchor)
    query = Reunion.query.order_by(Reunion.fecha.asc(), Reunion.hora_inicio.asc())
    if view_mode in ("day", "week", "month", "list", "area", "zone"):
        query = query.filter(Reunion.fecha >= start_date, Reunion.fecha <= end_date)
    if area_id:
        query = query.filter(Reunion.area_origen_id == area_id)
    if zone_id:
        query = query.filter(Reunion.zona_id == zone_id)
    meetings = query.all()
    meetings_by_day: dict[str, list[dict]] = {}
    for row in _meeting_rows_for_calendar(meetings):
        meetings_by_day.setdefault(row["meeting"].fecha.isoformat(), []).append(row)
    month_matrix = monthcalendar(anchor.year, anchor.month)
    grouped_rows: list[dict] = []
    if view_mode == "area":
        groups: dict[str, list[dict]] = {}
        for row in _meeting_rows_for_calendar(meetings):
            label = row["meeting"].area_origen.nombre
            groups.setdefault(label, []).append(row)
        grouped_rows = [{"label": key, "rows": value} for key, value in sorted(groups.items())]
    elif view_mode == "zone":
        groups = {}
        for row in _meeting_rows_for_calendar(meetings):
            label = row["meeting"].zona.nombre
            groups.setdefault(label, []).append(row)
        grouped_rows = [{"label": key, "rows": value} for key, value in sorted(groups.items())]
    return render_template(
        "admin/calendar.html",
        success=success,
        error=error,
        view_mode=view_mode,
        anchor=anchor,
        start_date=start_date,
        end_date=end_date,
        area_id=area_id,
        zone_id=zone_id,
        areas=Area.query.order_by(Area.nombre).all(),
        zones=ZonaReunion.query.order_by(ZonaReunion.nombre).all(),
        meetings=meetings,
        meetings_by_day=meetings_by_day,
        grouped_rows=grouped_rows,
        month_matrix=month_matrix,
        serialize_meeting=serialize_meeting,
    )


@web_bp.get("/web/admin/usuarios")
@require_roles(ROLE_ADMIN, api=False)
def admin_users():
    success, error = _request_messages()
    users = Usuario.query.order_by(Usuario.id).all()
    return render_template("admin/users.html", users=users, success=success, error=error)


@web_bp.route("/web/admin/usuarios/nuevo", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_users_new():
    success, error = _request_messages()
    form_data = _user_form_payload()
    if request.method == "POST":
        try:
            payload, role, area = _validate_user_form()
            password = payload["password_temporal"] or "Temporal123!"
            user = Usuario(
                nombre=payload["nombre"],
                correo=payload["correo"],
                telefono=payload["telefono"],
                password_hash=hash_password(password),
                role_id=role.id,
                area_id=area.id,
                estado=payload["estado"] if payload["estado"] in ("Activo", "Inactivo") else "Activo",
            )
            db.session.add(user)
            db.session.flush()
            log_event(
                "creacion_usuario",
                "usuario_web",
                "exitoso",
                entity_id=user.id,
                detail={
                    "target_user_nombre": user.nombre,
                    "area_nombre": user.area.nombre,
                    "role_nombre": user.role.nombre,
                },
            )
            db.session.commit()
            return _redirect_with_message("web.admin_users", success="Usuario creado.")
        except ValidationError as exc:
            error = exc.message
    context = _admin_base_context()
    return render_template("admin/user_form.html", form_data=form_data, success=success, error=error, is_new=True, **context)


@web_bp.route("/web/admin/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_users_edit(user_id: int):
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    success, error = _request_messages()
    form_data = _user_form_payload(user)
    if request.method == "POST":
        try:
            payload, role, area = _validate_user_form(user)
            user.nombre = payload["nombre"]
            user.correo = payload["correo"]
            user.telefono = payload["telefono"]
            user.role_id = role.id
            user.area_id = area.id
            user.estado = payload["estado"] if payload["estado"] in ("Activo", "Inactivo") else user.estado
            if payload["password_temporal"]:
                user.password_hash = hash_password(payload["password_temporal"])
            log_event(
                "edicion_usuario",
                "usuario_web",
                "exitoso",
                entity_id=user.id,
                detail={"target_user_nombre": user.nombre},
            )
            db.session.commit()
            return _redirect_with_message("web.admin_users", success="Usuario actualizado.")
        except ValidationError as exc:
            error = exc.message
            form_data = _user_form_payload(user)
    context = _admin_base_context()
    return render_template(
        "admin/user_form.html",
        form_data=form_data,
        success=success,
        error=error,
        is_new=False,
        user_record=user,
        **context,
    )


@web_bp.post("/web/admin/usuarios/<int:user_id>/desactivar")
@require_roles(ROLE_ADMIN, api=False)
def admin_users_disable(user_id: int):
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    user.estado = "Inactivo"
    log_event(
        "desactivacion_usuario",
        "usuario_web",
        "exitoso",
        entity_id=user.id,
        detail={"target_user_nombre": user.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_users", success="Usuario desactivado.")


@web_bp.post("/web/admin/usuarios/<int:user_id>/activar")
@require_roles(ROLE_ADMIN, api=False)
def admin_users_enable(user_id: int):
    user = Usuario.query.get(user_id)
    if not user:
        raise NotFoundError("Usuario no encontrado.")
    user.estado = "Activo"
    log_event(
        "activacion_usuario",
        "usuario_web",
        "exitoso",
        entity_id=user.id,
        detail={"target_user_nombre": user.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_users", success="Usuario activado.")


@web_bp.get("/web/admin/areas")
@require_roles(ROLE_ADMIN, api=False)
def admin_areas():
    success, error = _request_messages()
    areas = Area.query.order_by(Area.nombre).all()
    return render_template("admin/areas.html", areas=areas, success=success, error=error)


@web_bp.route("/web/admin/areas/nueva", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_areas_new():
    success, error = _request_messages()
    form_data = _area_form_payload()
    if request.method == "POST":
        try:
            payload = _area_form_payload()
            if not payload["nombre"]:
                raise ValidationError("Nombre es obligatorio.")
            if Area.query.filter_by(nombre=payload["nombre"]).first():
                raise ValidationError("Ya existe un area con ese nombre.")
            area = Area(nombre=payload["nombre"], descripcion=payload["descripcion"], estado=payload["estado"])
            db.session.add(area)
            db.session.flush()
            log_event(
                "creacion_area",
                "area_web",
                "exitoso",
                entity_id=area.id,
                detail={"area_nombre": area.nombre},
            )
            db.session.commit()
            return _redirect_with_message("web.admin_areas", success="Area creada.")
        except ValidationError as exc:
            error = exc.message
    return render_template("admin/area_form.html", form_data=form_data, success=success, error=error, is_new=True)


@web_bp.route("/web/admin/areas/<int:area_id>/editar", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_areas_edit(area_id: int):
    area = Area.query.get(area_id)
    if not area:
        raise NotFoundError("Area no encontrada.")
    success, error = _request_messages()
    form_data = _area_form_payload(area)
    if request.method == "POST":
        try:
            payload = _area_form_payload(area)
            if not payload["nombre"]:
                raise ValidationError("Nombre es obligatorio.")
            duplicate = Area.query.filter_by(nombre=payload["nombre"]).first()
            if duplicate and duplicate.id != area.id:
                raise ValidationError("Ya existe un area con ese nombre.")
            area.nombre = payload["nombre"]
            area.descripcion = payload["descripcion"]
            area.estado = payload["estado"] if payload["estado"] in ("Activa", "Inactiva") else area.estado
            log_event(
                "edicion_area",
                "area_web",
                "exitoso",
                entity_id=area.id,
                detail={"area_nombre": area.nombre},
            )
            db.session.commit()
            return _redirect_with_message("web.admin_areas", success="Area actualizada.")
        except ValidationError as exc:
            error = exc.message
            form_data = _area_form_payload(area)
    return render_template("admin/area_form.html", form_data=form_data, success=success, error=error, is_new=False, area_record=area)


@web_bp.post("/web/admin/areas/<int:area_id>/desactivar")
@require_roles(ROLE_ADMIN, api=False)
def admin_areas_disable(area_id: int):
    area = Area.query.get(area_id)
    if not area:
        raise NotFoundError("Area no encontrada.")
    area.estado = "Inactiva"
    log_event(
        "desactivacion_area",
        "area_web",
        "exitoso",
        entity_id=area.id,
        detail={"area_nombre": area.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_areas", success="Area desactivada.")


@web_bp.post("/web/admin/areas/<int:area_id>/activar")
@require_roles(ROLE_ADMIN, api=False)
def admin_areas_enable(area_id: int):
    area = Area.query.get(area_id)
    if not area:
        raise NotFoundError("Area no encontrada.")
    area.estado = "Activa"
    log_event(
        "activacion_area",
        "area_web",
        "exitoso",
        entity_id=area.id,
        detail={"area_nombre": area.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_areas", success="Area activada.")


@web_bp.get("/web/admin/zonas")
@require_roles(ROLE_ADMIN, api=False)
def admin_zones():
    success, error = _request_messages()
    zones = ZonaReunion.query.order_by(ZonaReunion.nombre).all()
    return render_template("admin/zones.html", zones=zones, success=success, error=error)


@web_bp.route("/web/admin/zonas/nueva", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_zones_new():
    success, error = _request_messages()
    form_data = _zone_form_payload()
    if request.method == "POST":
        try:
            payload = _zone_form_payload()
            if not payload["nombre"] or not payload["ubicacion"] or not payload["capacidad"]:
                raise ValidationError("Nombre, ubicacion y capacidad son obligatorios.")
            area_id = int(payload["area_id"]) if payload["area_id"] else None
            if area_id:
                area = Area.query.get(area_id)
                if not area:
                    raise ValidationError("Area invalida.")
            zone = ZonaReunion(
                nombre=payload["nombre"],
                ubicacion=payload["ubicacion"],
                capacidad=int(payload["capacidad"]),
                area_id=area_id,
                estado=payload["estado"],
                margen_operativo_minutos=int(payload["margen_operativo_minutos"]),
                descripcion=payload["descripcion"],
            )
            db.session.add(zone)
            db.session.flush()
            log_event(
                "creacion_zona",
                "zona_web",
                "exitoso",
                entity_id=zone.id,
                detail={"zona_nombre": zone.nombre, "capacidad": zone.capacidad},
            )
            db.session.commit()
            return _redirect_with_message("web.admin_zones", success="Zona creada.")
        except ValidationError as exc:
            error = exc.message
    return render_template("admin/zone_form.html", form_data=form_data, success=success, error=error, is_new=True, areas=Area.query.order_by(Area.nombre).all())


@web_bp.route("/web/admin/zonas/<int:zone_id>/editar", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_zones_edit(zone_id: int):
    zone = ZonaReunion.query.get(zone_id)
    if not zone:
        raise NotFoundError("Zona no encontrada.")
    success, error = _request_messages()
    form_data = _zone_form_payload(zone)
    if request.method == "POST":
        try:
            payload = _zone_form_payload(zone)
            if not payload["nombre"] or not payload["ubicacion"] or not payload["capacidad"]:
                raise ValidationError("Nombre, ubicacion y capacidad son obligatorios.")
            zone.nombre = payload["nombre"]
            zone.ubicacion = payload["ubicacion"]
            zone.capacidad = int(payload["capacidad"])
            zone.area_id = int(payload["area_id"]) if payload["area_id"] else None
            if zone.area_id and not Area.query.get(zone.area_id):
                raise ValidationError("Area invalida.")
            zone.estado = payload["estado"]
            zone.margen_operativo_minutos = int(payload["margen_operativo_minutos"])
            zone.descripcion = payload["descripcion"]
            log_event(
                "edicion_zona",
                "zona_web",
                "exitoso",
                entity_id=zone.id,
                detail={"zona_nombre": zone.nombre},
            )
            db.session.commit()
            return _redirect_with_message("web.admin_zones", success="Zona actualizada.")
        except ValidationError as exc:
            error = exc.message
            form_data = _zone_form_payload(zone)
    return render_template(
        "admin/zone_form.html",
        form_data=form_data,
        success=success,
        error=error,
        is_new=False,
        zone_record=zone,
        areas=Area.query.order_by(Area.nombre).all(),
    )


@web_bp.post("/web/admin/zonas/<int:zone_id>/desactivar")
@require_roles(ROLE_ADMIN, api=False)
def admin_zones_disable(zone_id: int):
    zone = ZonaReunion.query.get(zone_id)
    if not zone:
        raise NotFoundError("Zona no encontrada.")
    zone.estado = "Inactiva"
    log_event(
        "desactivacion_zona",
        "zona_web",
        "exitoso",
        entity_id=zone.id,
        detail={"zona_nombre": zone.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_zones", success="Zona desactivada.")


@web_bp.post("/web/admin/zonas/<int:zone_id>/activar")
@require_roles(ROLE_ADMIN, api=False)
def admin_zones_enable(zone_id: int):
    zone = ZonaReunion.query.get(zone_id)
    if not zone:
        raise NotFoundError("Zona no encontrada.")
    zone.estado = "Activa"
    log_event(
        "activacion_zona",
        "zona_web",
        "exitoso",
        entity_id=zone.id,
        detail={"zona_nombre": zone.nombre},
    )
    db.session.commit()
    return _redirect_with_message("web.admin_zones", success="Zona activada.")


@web_bp.get("/web/admin/reuniones")
@require_roles(*OPERATOR_ROLES, api=False)
def admin_meetings():
    success, error = _request_messages()
    meetings = Reunion.query.order_by(Reunion.fecha.desc(), Reunion.hora_inicio.desc()).all()
    return render_template("admin/meetings.html", meetings=meetings, serialize_meeting=serialize_meeting, success=success, error=error)


@web_bp.route("/web/admin/reuniones/nueva", methods=["GET", "POST"])
@require_roles(*OPERATOR_ROLES, api=False)
def admin_meetings_new():
    success, error = _request_messages()
    form_data = _meeting_form_payload()
    if request.method == "POST":
        try:
            meeting = create_meeting(_meeting_form_payload())
            return _redirect_with_message("web.admin_meeting_detail", meeting_id=meeting.id, success="Reunion creada.")
        except (ValidationError, ConflictError, ForbiddenError) as exc:
            error = exc.message
    active_users = Usuario.query.filter_by(estado="Activo").order_by(Usuario.nombre).all()
    active_zones = ZonaReunion.query.filter(ZonaReunion.estado != "Inactiva").order_by(ZonaReunion.nombre).all()
    selected_participants = _selected_participant_cards(form_data["participant_ids"])
    return render_template(
        "admin/meeting_form.html",
        form_data=form_data,
        success=success,
        error=error,
        is_new=True,
        participants=active_users,
        responsible_candidates=active_users,
        zones=active_zones,
        selected_participants=selected_participants,
        searchable_areas=Area.query.filter_by(estado="Activa").order_by(Area.nombre).all(),
        user_search_locked_area_id=None,
    )


@web_bp.get("/web/admin/reuniones/<int:meeting_id>")
@require_roles(*OPERATOR_ROLES, api=False)
def admin_meeting_detail(meeting_id: int):
    success, error = _request_messages()
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    related_logs = (
        LogSistema.query.filter(
            (LogSistema.entidad == "reunion")
            | ((LogSistema.entidad == "reunion_participante") & (LogSistema.detalle_seguro.like(f"%\"reunion_id\": {meeting.id}%")))
        )
        .order_by(LogSistema.fecha_hora.desc())
        .limit(50)
        .all()
    )
    return render_template("admin/meeting_detail.html", meeting=meeting, meeting_data=serialize_meeting(meeting), logs=related_logs, success=success, error=error)


@web_bp.route("/web/admin/reuniones/<int:meeting_id>/editar", methods=["GET", "POST"])
@require_roles(*OPERATOR_ROLES, api=False)
def admin_meetings_edit(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    success, error = _request_messages()
    form_data = _meeting_form_payload(meeting)
    if request.method == "POST":
        try:
            updated = update_meeting(meeting, _meeting_form_payload(meeting))
            return _redirect_with_message("web.admin_meeting_detail", meeting_id=updated.id, success="Reunion actualizada.")
        except (ValidationError, ConflictError, ForbiddenError) as exc:
            error = exc.message
            form_data = _meeting_form_payload(meeting)
    active_users = Usuario.query.filter_by(estado="Activo").order_by(Usuario.nombre).all()
    active_zones = ZonaReunion.query.filter(ZonaReunion.estado != "Inactiva").order_by(ZonaReunion.nombre).all()
    selected_participants = _selected_participant_cards(form_data["participant_ids"])
    return render_template(
        "admin/meeting_form.html",
        form_data=form_data,
        success=success,
        error=error,
        is_new=False,
        meeting=meeting,
        participants=active_users,
        responsible_candidates=active_users,
        zones=active_zones,
        selected_participants=selected_participants,
        searchable_areas=Area.query.filter_by(estado="Activa").order_by(Area.nombre).all(),
        user_search_locked_area_id=None,
    )


@web_bp.post("/web/admin/reuniones/<int:meeting_id>/cancelar")
@require_roles(*OPERATOR_ROLES, api=False)
def admin_meetings_cancel(meeting_id: int):
    meeting = Reunion.query.get(meeting_id)
    if not meeting:
        raise NotFoundError("Reunion no encontrada.")
    cancel_meeting(meeting)
    return _redirect_with_message("web.admin_meeting_detail", meeting_id=meeting.id, success="Reunion cancelada.")


@web_bp.get("/web/admin/logs")
@require_roles(ROLE_ADMIN, api=False)
def admin_logs():
    success, error = _request_messages()
    logs = LogSistema.query.order_by(LogSistema.fecha_hora.desc()).limit(200).all()
    return render_template("admin/logs.html", logs=logs, success=success, error=error)


@web_bp.route("/web/admin/configuracion", methods=["GET", "POST"])
@require_roles(ROLE_ADMIN, api=False)
def admin_config():
    success, error = _request_messages()
    items = Configuracion.query.order_by(Configuracion.clave).all()
    if request.method == "POST":
        editable_keys = {
            "descanso_persona_minutos",
            "margen_zona_minutos",
            "horario_laboral_inicio",
            "horario_laboral_fin",
            "max_intentos_login",
            "debug_mode",
            "correo_formal_automatico",
            "recordatorio_30_minutos",
            "recordatorio_10_minutos",
        }
        for item in items:
            if item.clave in editable_keys:
                item.valor = request.form.get(item.clave, item.valor).strip()
        log_event("edicion_configuracion", "configuracion_web", "exitoso")
        db.session.commit()
        return _redirect_with_message("web.admin_config", success="Configuracion actualizada.")
    return render_template("admin/config.html", items=items, success=success, error=error)


@web_bp.get("/scheduler")
@require_roles(ROLE_ADMIN, ROLE_SECRETARIA, api=False)
def scheduler_dashboard():
    actor = g.current_user
    query = Reunion.query.order_by(Reunion.fecha.desc()).limit(20)
    meetings = query.all() if actor.role.nombre == ROLE_SECRETARIA else query.all()
    users = Usuario.query.count() if actor.role.nombre == ROLE_SECRETARIA else Usuario.query.filter_by(area_id=actor.area_id).count()
    zones = ZonaReunion.query.filter_by(estado="Activa").count()
    return render_template(
        "scheduler/dashboard.html",
        meetings=meetings,
        users_count=users,
        zones_count=zones,
        area_name=actor.area.nombre,
    )


@web_bp.get("/scheduler/usuarios")
@require_roles(ROLE_SECRETARIA, api=False)
def scheduler_users():
    users = Usuario.query.order_by(Usuario.id).all()
    return render_template("scheduler/users.html", users=users)


@web_bp.get("/scheduler/reuniones")
@require_roles(ROLE_SECRETARIA, api=False)
def scheduler_meetings():
    meetings = Reunion.query.order_by(Reunion.fecha.desc()).all()
    return render_template("scheduler/meetings.html", meetings=meetings)


@web_bp.get("/scheduler/respuestas")
@require_roles(ROLE_SECRETARIA, api=False)
def scheduler_responses():
    meetings = Reunion.query.order_by(Reunion.fecha.desc()).all()
    return render_template("scheduler/responses.html", meetings=meetings)


@web_bp.get("/scheduler/zonas")
@require_roles(ROLE_SECRETARIA, api=False)
def scheduler_zones():
    zones = ZonaReunion.query.filter_by(estado="Activa").order_by(ZonaReunion.nombre).all()
    return render_template("scheduler/zones.html", zones=zones)


@web_bp.get("/mis-reuniones")
@require_auth(api=False)
def user_dashboard():
    meetings = Reunion.query.filter(Reunion.participantes.any(usuario_id=g.current_user.id)).all()
    return render_template("scheduler/meetings.html", meetings=meetings)


@web_bp.get("/api/web/availability")
@require_auth(api=True)
def api_availability():
    from flask import jsonify
    fecha_str = request.args.get("fecha")
    hora_inicio_str = request.args.get("hora_inicio")
    hora_fin_str = request.args.get("hora_fin")
    if not fecha_str or not hora_inicio_str or not hora_fin_str:
        return jsonify({"error": "Faltan parametros fecha, hora_inicio, hora_fin"}), 400
    try:
        from app.services.meeting_requests import check_availability
        import datetime
        fecha = datetime.date.fromisoformat(fecha_str)
        hora_inicio = datetime.datetime.strptime(hora_inicio_str, "%H:%M").time()
        hora_fin = datetime.datetime.strptime(hora_fin_str, "%H:%M").time()
        data = check_availability(fecha, hora_inicio, hora_fin)
        
        grouped_users = {}
        for u in data["usuarios"]:
            grouped_users.setdefault(u["area_nombre"], []).append({
                "id": u["id"],
                "nombre": u["nombre"],
                "correo": u["correo"],
                "disponible": u["disponible"],
                "motivo": u["motivo"]
            })
        
        return jsonify({
            "fecha": data["fecha"],
            "hora_inicio": data["hora_inicio"],
            "hora_fin": data["hora_fin"],
            "zonas": data["zonas"],
            "usuarios_por_area": grouped_users
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@web_bp.get("/web/solicitudes")
@require_auth(api=False)
def solicitudes_list():
    from app.models import ReunionSolicitud
    actor = g.current_user
    if actor.role.nombre in (ROLE_SECRETARIA, ROLE_ADMIN):
        return redirect(url_for("web.secretaria_solicitudes"))
        
    solicitudes = ReunionSolicitud.query.filter_by(solicitante_usuario_id=actor.id).order_by(ReunionSolicitud.created_at.desc()).all()
    success, error = _request_messages()
    return render_template(
        "scheduler/requests_list.html",
        solicitudes=solicitudes,
        success=success,
        error=error
    )


@web_bp.get("/web/solicitudes/nueva")
@require_roles(ROLE_AGENDADOR, ROLE_COLABORADOR, api=False)
def nueva_solicitud():
    actor = g.current_user
    active_zones = ZonaReunion.query.filter_by(estado="Activa").order_by(ZonaReunion.nombre).all()
    if actor.role.nombre == ROLE_AGENDADOR:
        active_zones = [z for z in active_zones if z.area_id in (actor.area_id, None)]
        
    if actor.role.nombre == ROLE_AGENDADOR:
        users = Usuario.query.filter_by(area_id=actor.area_id, estado="Activo").order_by(Usuario.nombre).all()
    else:
        users = Usuario.query.filter_by(estado="Activo").order_by(Usuario.nombre).all()
        
    success, error = _request_messages()
    return render_template(
        "scheduler/request_form.html",
        zones=active_zones,
        users=users,
        success=success,
        error=error
    )


@web_bp.post("/web/solicitudes/nueva")
@require_roles(ROLE_AGENDADOR, ROLE_COLABORADOR, api=False)
def crear_solicitud_post():
    actor = g.current_user
    try:
        from app.services.meeting_requests import create_meeting_request
        payload = {
            "titulo": request.form.get("titulo", "").strip(),
            "motivo": request.form.get("motivo", "").strip(),
            "zona_id": request.form.get("zona_id"),
            "fecha": request.form.get("fecha"),
            "hora_inicio": request.form.get("hora_inicio"),
            "hora_fin": request.form.get("hora_fin"),
            "participant_ids": request.form.getlist("participant_ids"),
            "observacion_solicitante": request.form.get("observacion_solicitante", "").strip()
        }
        create_meeting_request(payload, actor)
        return _redirect_with_message("web.solicitudes_list", success="Solicitud de reunión creada exitosamente.")
    except Exception as e:
        return _redirect_with_message("web.nueva_solicitud", error=str(e))


@web_bp.get("/web/solicitudes/<int:sol_id>")
@require_auth(api=False)
def solicitud_detail(sol_id: int):
    from app.models import ReunionSolicitud
    sol = ReunionSolicitud.query.get_or_404(sol_id)
    actor = g.current_user
    if sol.solicitante_usuario_id != actor.id and actor.role.nombre not in (ROLE_SECRETARIA, ROLE_ADMIN):
        return render_template("errors/unauthorized.html", message="Su cuenta no tiene acceso a este módulo.")
        
    success, error = _request_messages()
    return render_template(
        "scheduler/request_detail.html",
        solicitud=sol,
        success=success,
        error=error
    )


@web_bp.post("/web/solicitudes/<int:sol_id>/cancelar")
@require_auth(api=False)
def cancelar_solicitud(sol_id: int):
    actor = g.current_user
    try:
        from app.services.meeting_requests import cancel_own_meeting_request
        cancel_own_meeting_request(sol_id, actor)
        return _redirect_with_message("web.solicitudes_list", success="Solicitud cancelada exitosamente.")
    except Exception as e:
        return _redirect_with_message("web.solicitudes_list", error=str(e))


@web_bp.get("/web/secretaria/solicitudes")
@require_roles(ROLE_SECRETARIA, ROLE_ADMIN, api=False)
def secretaria_solicitudes():
    from app.models import ReunionSolicitud
    solicitudes_pendientes = ReunionSolicitud.query.filter_by(estado="Pendiente").order_by(ReunionSolicitud.created_at.desc()).all()
    solicitudes_revisadas = ReunionSolicitud.query.filter(ReunionSolicitud.estado != "Pendiente").order_by(ReunionSolicitud.updated_at.desc()).all()
    success, error = _request_messages()
    return render_template(
        "scheduler/secretaria_requests.html",
        pendientes=solicitudes_pendientes,
        revisadas=solicitudes_revisadas,
        success=success,
        error=error
    )


@web_bp.get("/web/secretaria/solicitudes/<int:sol_id>")
@require_roles(ROLE_SECRETARIA, ROLE_ADMIN, api=False)
def secretaria_solicitud_review(sol_id: int):
    from app.models import ReunionSolicitud
    sol = ReunionSolicitud.query.get_or_404(sol_id)
    success, error = _request_messages()
    
    from app.services.meeting_requests import check_availability
    availability = check_availability(sol.fecha, sol.hora_inicio, sol.hora_fin)
    
    zone_status = next((z for z in availability["zonas"] if z["id"] == sol.zona_id), None)
    
    participant_ids = [p.usuario_id for p in sol.participantes]
    participants_status = [u for u in availability["usuarios"] if u["id"] in participant_ids]
    
    can_approve = (zone_status and zone_status["disponible"]) and all(u["disponible"] for u in participants_status)
    if sol.solicitante_usuario_id == g.current_user.id:
        can_approve = False
        
    return render_template(
        "scheduler/secretaria_request_review.html",
        solicitud=sol,
        zone_status=zone_status,
        participants_status=participants_status,
        can_approve=can_approve,
        success=success,
        error=error
    )


@web_bp.post("/web/secretaria/solicitudes/<int:sol_id>/aprobar")
@require_roles(ROLE_SECRETARIA, ROLE_ADMIN, api=False)
def secretaria_solicitud_aprobar(sol_id: int):
    actor = g.current_user
    try:
        from app.services.meeting_requests import approve_meeting_request
        approve_meeting_request(sol_id, actor)
        return _redirect_with_message("web.secretaria_solicitudes", success="Solicitud aprobada y reunión agendada exitosamente.")
    except Exception as e:
        return _redirect_with_message("web.secretaria_solicitud_review", sol_id=sol_id, error=str(e))


@web_bp.post("/web/secretaria/solicitudes/<int:sol_id>/rechazar")
@require_roles(ROLE_SECRETARIA, ROLE_ADMIN, api=False)
def secretaria_solicitud_rechazar(sol_id: int):
    actor = g.current_user
    reason = request.form.get("reason", "").strip()
    try:
        from app.services.meeting_requests import reject_meeting_request
        reject_meeting_request(sol_id, actor, reason)
        return _redirect_with_message("web.secretaria_solicitudes", success="Solicitud rechazada exitosamente.")
    except Exception as e:
        return _redirect_with_message("web.secretaria_solicitud_review", sol_id=sol_id, error=str(e))
