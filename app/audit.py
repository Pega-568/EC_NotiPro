import json

from flask import Request, g, request

from app.extensions import db
from app.models import LogSistema


def _safe_json(detail: dict | None) -> str | None:
    if not detail:
        return None
    return json.dumps(detail, ensure_ascii=True, sort_keys=True)[:1000]


def _humanize(action: str, entity: str, result: str, actor_name: str, detail: dict | None) -> str:
    detail = detail or {}
    user_name = detail.get("target_user_nombre") or detail.get("user_nombre")
    area_name = detail.get("area_nombre")
    role_name = detail.get("role_nombre")
    zone_name = detail.get("zona_nombre")
    meeting_title = detail.get("meeting_title") or detail.get("titulo")
    meeting_date = detail.get("meeting_fecha")
    start = detail.get("meeting_hora_inicio")
    end = detail.get("meeting_hora_fin")
    participant_names = detail.get("participant_names") or []
    reason = detail.get("razon_rechazo")
    route = detail.get("ruta")
    attempted = detail.get("accion_intentada")

    if action == "login":
        return f"{actor_name} inicio sesion."
    if action == "logout":
        return f"{actor_name} cerro sesion."
    if action == "login_fallido":
        return f"Se registro un intento fallido de inicio de sesion para {detail.get('correo', 'usuario desconocido')}."
    if action == "creacion_usuario":
        return f"{actor_name} creo el usuario '{user_name}' en el area {area_name} con rol {role_name}."
    if action == "edicion_usuario":
        return f"{actor_name} edito el usuario '{user_name}'."
    if action == "desactivacion_usuario":
        return f"{actor_name} desactivo el usuario '{user_name}'."
    if action == "activacion_usuario":
        return f"{actor_name} activo el usuario '{user_name}'."
    if action == "creacion_area":
        return f"{actor_name} creo el area '{area_name}'."
    if action == "edicion_area":
        return f"{actor_name} edito el area '{area_name}'."
    if action == "desactivacion_area":
        return f"{actor_name} desactivo el area '{area_name}'."
    if action == "activacion_area":
        return f"{actor_name} activo el area '{area_name}'."
    if action == "creacion_zona":
        return f"{actor_name} creo la zona de reunion '{zone_name}', capacidad {detail.get('capacidad', '?')} personas."
    if action == "edicion_zona":
        return f"{actor_name} edito la zona de reunion '{zone_name}'."
    if action == "desactivacion_zona":
        return f"{actor_name} desactivo la zona de reunion '{zone_name}'."
    if action == "activacion_zona":
        return f"{actor_name} activo la zona de reunion '{zone_name}'."
    if action == "creacion_reunion":
        names = ", ".join(participant_names) if participant_names else "sin participantes"
        return (
            f"{actor_name} creo la reunion '{meeting_title}' para el {meeting_date} "
            f"de {start} a {end} en {zone_name} con {names}."
        )
    if action == "creacion_reunion_interna":
        names = ", ".join(participant_names) if participant_names else "sin participantes"
        return (
            f"{actor_name} creo la reunion interna '{meeting_title}' para el {meeting_date} "
            f"de {start} a {end} en {zone_name} con {names}."
        )
    if action == "rechazo_reunion_interna":
        return f"Se rechazo la creacion de una reunion interna solicitada por {actor_name}: {detail.get('motivo')}."
    if action == "modificacion_reunion":
        return f"{actor_name} edito la reunion '{meeting_title}'."
    if action == "cancelacion_reunion":
        return (
            f"{actor_name} cancelo la reunion '{meeting_title}', programada para el {meeting_date} "
            f"de {start} a {end}."
        )
    if action == "aceptacion_reunion":
        return f"{actor_name} acepto la reunion '{meeting_title}'."
    if action == "rechazo_reunion":
        return f"{actor_name} rechazo la reunion '{meeting_title}'. Razon: {reason}."
    if action == "intento_no_autorizado":
        return f"{actor_name} intento acceder a una accion no permitida: {attempted or route or entity}."
    if action == "error_validacion":
        return f"Se rechazo una solicitud por validacion: {detail.get('error', 'error de validacion')}."
    if action == "edicion_configuracion":
        return f"{actor_name} actualizo la configuracion del sistema."
    if action == "registro_device_token":
        return f"{actor_name} registro o actualizo un dispositivo movil para notificaciones."
    return f"{actor_name} ejecuto la accion {action} sobre {entity} con resultado {result}."


def log_event(
    action: str,
    entity: str,
    result: str,
    *,
    entity_id: str | int | None = None,
    detail: dict | None = None,
    description_humana: str | None = None,
    req: Request | None = None,
) -> None:
    req = req or request
    actor = getattr(g, "current_user", None)
    actor_name = getattr(actor, "nombre", None) or "Sistema"
    entry = LogSistema(
        usuario_actor_id=getattr(actor, "id", None),
        rol_actor=getattr(getattr(actor, "role", None), "nombre", None),
        accion=action,
        entidad=entity,
        entidad_id=str(entity_id) if entity_id is not None else None,
        resultado=result,
        descripcion_humana=description_humana or _humanize(action, entity, result, actor_name, detail),
        detalle_seguro=_safe_json(detail),
        ip=req.headers.get("X-Forwarded-For", req.remote_addr),
        user_agent=req.headers.get("User-Agent", "")[:255],
    )
    db.session.add(entry)
