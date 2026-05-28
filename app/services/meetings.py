from __future__ import annotations

from datetime import date, datetime, time, timedelta

from flask import g
from sqlalchemy import and_, or_

from app.audit import log_event
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Configuracion, Reunion, ReunionParticipante, Usuario, ZonaReunion
from app.services.notifications import queue_meeting_notifications


def _config_int(key: str, default: int) -> int:
    setting = Configuracion.query.filter_by(clave=key).first()
    return int(setting.valor) if setting else default


def _config_time(key: str, default: str) -> time:
    setting = Configuracion.query.filter_by(clave=key).first()
    value = setting.valor if setting else default
    return datetime.strptime(value, "%H:%M").time()


def _combine(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock)


def _meeting_window(fecha: date, hora_inicio: time, hora_fin: time):
    start_dt = _combine(fecha, hora_inicio)
    end_dt = _combine(fecha, hora_fin)
    return start_dt, end_dt


def _validate_participants(participant_ids: list[int]) -> list[Usuario]:
    if not participant_ids:
        raise ValidationError("Debe incluir al menos un participante.")
    if len(participant_ids) != len(set(participant_ids)):
        raise ValidationError("No se permiten participantes duplicados.")
    users = Usuario.query.filter(Usuario.id.in_(participant_ids)).all()
    if len(users) != len(participant_ids):
        raise ValidationError("Hay participantes inexistentes.")
    if any(user.estado != "Activo" for user in users):
        raise ValidationError("Todos los participantes deben estar activos.")
    return users


def _validate_actor_scope(actor, participants: list[Usuario]) -> None:
    area_ids = {user.area_id for user in participants}
    area_ids.add(actor.area_id)
    if actor.role.nombre == "Agendador":
        if any(user.area_id != actor.area_id for user in participants):
            raise ForbiddenError("Agendador solo puede convocar usuarios de su misma area.")
    if len(area_ids) > 1 and actor.role.nombre != "Admin":
        raise ForbiddenError("Solo Admin puede crear reuniones multi area.")


def _validate_basic_schedule(fecha: date, hora_inicio: time, hora_fin: time) -> None:
    today = date.today()
    if fecha < today:
        raise ValidationError("La fecha no puede estar en el pasado.")
    if hora_fin <= hora_inicio:
        raise ValidationError("hora_fin debe ser mayor que hora_inicio.")
    duration = _combine(fecha, hora_fin) - _combine(fecha, hora_inicio)
    if duration < timedelta(minutes=15) or duration > timedelta(hours=8):
        raise ValidationError("La duracion debe estar entre 15 minutos y 8 horas.")
    work_start = _config_time("horario_laboral_inicio", "08:00")
    work_end = _config_time("horario_laboral_fin", "17:00")
    if hora_inicio < work_start or hora_fin > work_end:
        raise ValidationError("La reunion debe estar dentro del horario laboral configurado.")


def _find_zone(zona_id: int) -> ZonaReunion:
    zone = ZonaReunion.query.get(zona_id)
    if not zone:
        raise ValidationError("Zona inexistente.")
    if zone.estado != "Activa":
        raise ValidationError("Solo se pueden usar zonas activas.")
    return zone


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _validate_zone_conflicts(
    zone: ZonaReunion,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    *,
    meeting_id: int | None = None,
) -> None:
    start_dt, end_dt = _meeting_window(fecha, hora_inicio, hora_fin)
    global_margin = _config_int("margen_zona_minutos", 5)
    margin = max(zone.margen_operativo_minutos, global_margin)
    meetings = Reunion.query.filter(
        Reunion.zona_id == zone.id,
        Reunion.fecha == fecha,
        Reunion.estado != "Cancelada",
    ).all()
    for meeting in meetings:
        if meeting_id and meeting.id == meeting_id:
            continue
        other_start, other_end = _meeting_window(meeting.fecha, meeting.hora_inicio, meeting.hora_fin)
        other_start -= timedelta(minutes=margin)
        other_end += timedelta(minutes=margin)
        if _overlaps(start_dt, end_dt, other_start, other_end):
            raise ConflictError("La zona ya esta reservada en ese horario o margen operativo.")


def _validate_person_conflicts(
    participant_ids: list[int],
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    *,
    meeting_id: int | None = None,
) -> None:
    start_dt, end_dt = _meeting_window(fecha, hora_inicio, hora_fin)
    rest_minutes = _config_int("descanso_persona_minutos", 10)
    rows = (
        db.session.query(ReunionParticipante, Reunion)
        .join(Reunion, Reunion.id == ReunionParticipante.reunion_id)
        .filter(
            ReunionParticipante.usuario_id.in_(participant_ids),
            Reunion.fecha == fecha,
            Reunion.estado != "Cancelada",
        )
        .all()
    )
    for participant_row, meeting in rows:
        if meeting_id and meeting.id == meeting_id:
            continue
        other_start, other_end = _meeting_window(meeting.fecha, meeting.hora_inicio, meeting.hora_fin)
        other_start -= timedelta(minutes=rest_minutes)
        other_end += timedelta(minutes=rest_minutes)
        if _overlaps(start_dt, end_dt, other_start, other_end):
            raise ConflictError(
                f"El usuario {participant_row.usuario_id} ya tiene otra reunion en ese horario."
            )


def serialize_meeting(meeting: Reunion) -> dict:
    accepted = sum(1 for item in meeting.participantes if item.estado_respuesta == "Aceptada")
    rejected = sum(1 for item in meeting.participantes if item.estado_respuesta == "Rechazada")
    pending = sum(1 for item in meeting.participantes if item.estado_respuesta == "Pendiente")
    if meeting.estado == "Cancelada":
        visual_status = "Cancelada"
    elif rejected > 0:
        visual_status = "Rechazada"
    elif accepted > 0 and pending > 0:
        visual_status = "Parcialmente respondida"
    elif accepted == len(meeting.participantes) and accepted > 0:
        visual_status = "Aceptada"
    else:
        visual_status = "Pendiente"
    return {
        "id": meeting.id,
        "titulo": meeting.titulo,
        "motivo": meeting.motivo,
        "creador_id": meeting.creador_id,
        "creador_nombre": meeting.creador.nombre,
        "area_origen_id": meeting.area_origen_id,
        "zona_id": meeting.zona_id,
        "zona_nombre": meeting.zona.nombre,
        "fecha": meeting.fecha.isoformat(),
        "hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
        "hora_fin": meeting.hora_fin.strftime("%H:%M"),
        "estado": meeting.estado,
        "estado_visual": visual_status,
        "prioridad": meeting.prioridad,
        "resumen_respuestas": {
            "aceptadas": accepted,
            "rechazadas": rejected,
            "pendientes": pending,
            "total": len(meeting.participantes),
        },
        "participantes": [
            {
                "usuario_id": item.usuario_id,
                "nombre": item.usuario.nombre,
                "correo": item.usuario.correo,
                "estado_respuesta": item.estado_respuesta,
                "razon_rechazo": item.razon_rechazo,
                "fecha_respuesta": item.fecha_respuesta.isoformat() if item.fecha_respuesta else None,
            }
            for item in meeting.participantes
        ],
        "created_at": meeting.created_at.isoformat(),
        "updated_at": meeting.updated_at.isoformat(),
    }


def create_meeting(payload: dict) -> Reunion:
    actor = g.current_user
    if actor.role.nombre not in ("Admin", "Agendador"):
        raise ForbiddenError("No tiene permiso para crear reuniones.")
    required = ("titulo", "motivo", "zona_id", "fecha", "hora_inicio", "hora_fin", "participant_ids")
    missing = [field for field in required if field not in payload or payload.get(field) in (None, "", [])]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")
    participant_ids = [int(value) for value in payload.get("participant_ids", [])]
    participants = _validate_participants(participant_ids)
    _validate_actor_scope(actor, participants)

    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()
    _validate_basic_schedule(fecha, hora_inicio, hora_fin)
    zone = _find_zone(int(payload["zona_id"]))
    _validate_zone_conflicts(zone, fecha, hora_inicio, hora_fin)
    _validate_person_conflicts(participant_ids, fecha, hora_inicio, hora_fin)

    meeting = Reunion(
        titulo=payload["titulo"].strip(),
        motivo=payload["motivo"].strip(),
        creador_id=actor.id,
        area_origen_id=actor.area_id,
        zona_id=zone.id,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        estado="Pendiente",
        prioridad=payload.get("prioridad", "Media"),
    )
    db.session.add(meeting)
    db.session.flush()
    for participant in participants:
        db.session.add(
            ReunionParticipante(
                reunion_id=meeting.id,
                usuario_id=participant.id,
                estado_respuesta="Pendiente",
            )
        )
    log_event(
        "creacion_reunion",
        "reunion",
        "exitoso",
        entity_id=meeting.id,
        detail={
            "participantes": participant_ids,
            "participant_names": [participant.nombre for participant in participants],
            "zona_id": zone.id,
            "zona_nombre": zone.nombre,
            "meeting_title": meeting.titulo,
            "meeting_fecha": meeting.fecha.strftime("%d/%m/%Y"),
            "meeting_hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
            "meeting_hora_fin": meeting.hora_fin.strftime("%H:%M"),
        },
    )
    queue_meeting_notifications(meeting, "meeting_created")
    db.session.commit()
    return meeting


def update_meeting(meeting: Reunion, payload: dict) -> Reunion:
    actor = g.current_user
    if actor.role.nombre != "Admin":
        raise ForbiddenError("Solo Admin puede modificar reuniones.")
    if meeting.estado == "Cancelada":
        raise ValidationError("No se puede editar una reunion cancelada.")
    required = ("titulo", "motivo", "zona_id", "fecha", "hora_inicio", "hora_fin", "participant_ids")
    missing = [field for field in required if field not in payload or payload.get(field) in (None, "", [])]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")

    participant_ids = [int(value) for value in payload.get("participant_ids", [])]
    participants = _validate_participants(participant_ids)
    _validate_actor_scope(actor, participants)
    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()
    _validate_basic_schedule(fecha, hora_inicio, hora_fin)
    zone = _find_zone(int(payload["zona_id"]))
    _validate_zone_conflicts(zone, fecha, hora_inicio, hora_fin, meeting_id=meeting.id)
    _validate_person_conflicts(participant_ids, fecha, hora_inicio, hora_fin, meeting_id=meeting.id)

    meeting.titulo = payload["titulo"].strip()
    meeting.motivo = payload["motivo"].strip()
    meeting.zona_id = zone.id
    meeting.fecha = fecha
    meeting.hora_inicio = hora_inicio
    meeting.hora_fin = hora_fin
    meeting.prioridad = payload.get("prioridad", meeting.prioridad)
    meeting.participantes.clear()
    db.session.flush()
    for participant in participants:
        db.session.add(
            ReunionParticipante(
                reunion_id=meeting.id,
                usuario_id=participant.id,
                estado_respuesta="Pendiente",
            )
        )
    log_event(
        "modificacion_reunion",
        "reunion",
        "exitoso",
        entity_id=meeting.id,
        detail={"meeting_title": meeting.titulo},
    )
    queue_meeting_notifications(meeting, "meeting_updated")
    db.session.commit()
    return meeting


def cancel_meeting(meeting: Reunion) -> Reunion:
    actor = g.current_user
    if actor.role.nombre != "Admin":
        raise ForbiddenError("Solo Admin puede cancelar reuniones.")
    meeting.estado = "Cancelada"
    log_event(
        "cancelacion_reunion",
        "reunion",
        "exitoso",
        entity_id=meeting.id,
        detail={
            "meeting_title": meeting.titulo,
            "meeting_fecha": meeting.fecha.strftime("%d/%m/%Y"),
            "meeting_hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
            "meeting_hora_fin": meeting.hora_fin.strftime("%H:%M"),
        },
    )
    queue_meeting_notifications(meeting, "meeting_canceled")
    db.session.commit()
    return meeting


def respond_to_meeting(meeting: Reunion, *, accept: bool, reason: str | None = None) -> ReunionParticipante:
    actor = g.current_user
    item = next((row for row in meeting.participantes if row.usuario_id == actor.id), None)
    if not item:
        raise ForbiddenError("No participa en esta reunion.")
    if meeting.estado == "Cancelada":
        raise ValidationError("No puede responder una reunion cancelada.")
    if accept:
        item.estado_respuesta = "Aceptada"
        item.razon_rechazo = None
        action = "aceptacion_reunion"
    else:
        if not reason or not reason.strip():
            raise ValidationError("Debe indicar una razon de rechazo.")
        item.estado_respuesta = "Rechazada"
        item.razon_rechazo = reason.strip()
        action = "rechazo_reunion"
    item.fecha_respuesta = datetime.utcnow()
    if any(row.estado_respuesta == "Rechazada" for row in meeting.participantes):
        meeting.estado = "Rechazada"
    elif all(row.estado_respuesta == "Aceptada" for row in meeting.participantes):
        meeting.estado = "Aceptada"
    else:
        meeting.estado = "Pendiente"
    log_event(
        action,
        "reunion_participante",
        "exitoso",
        entity_id=item.id,
        detail={
            "reunion_id": meeting.id,
            "meeting_title": meeting.titulo,
            "razon_rechazo": item.razon_rechazo,
        },
    )
    db.session.commit()
    return item
