from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from flask import g

from app.audit import log_event
from app.constants import OPERATOR_ROLES, ROLE_AGENDADOR
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.extensions import db
from app.models import (
    Configuracion,
    Reunion,
    ReunionHistorial,
    ReunionParticipante,
    Usuario,
    ZonaReunion,
)
from app.services.notifications import (
    dispatch_due_communications,
    queue_meeting_emails,
    queue_meeting_notifications,
)


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


def _validate_actor_scope(actor: Usuario) -> None:
    if actor.role.nombre not in OPERATOR_ROLES:
        raise ForbiddenError("No tiene permiso para crear o editar reuniones.")


def _validate_responsable(
    responsable_reunion_id: int, participants: list[Usuario], actor: Usuario
) -> Usuario:
    responsable = Usuario.query.get(responsable_reunion_id)
    if not responsable or responsable.estado != "Activo":
        raise ValidationError("Debe seleccionar un responsable de reunion activo.")
    participant_ids = {user.id for user in participants}
    if responsable.id not in participant_ids:
        raise ValidationError(
            "El responsable de la reunión debe estar incluido en la lista de participantes."
        )
    return responsable


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
        "responsable_reunion_id": meeting.responsable_reunion_id,
        "responsable_reunion_nombre": meeting.responsable.nombre,
        "responsable_reunion_correo": meeting.responsable.correo,
        "area_origen_id": meeting.area_origen_id,
        "area_origen_nombre": meeting.area_origen.nombre,
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


def sync_meeting_participants(meeting: Reunion, new_participant_ids: list[int]) -> None:
    old_items = {item.usuario_id: item for item in meeting.participantes}
    old_ids = set(old_items.keys())
    new_ids = set(new_participant_ids)
    
    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    
    for uid in removed_ids:
        db.session.delete(old_items[uid])
        
    for uid in added_ids:
        db.session.add(
            ReunionParticipante(
                reunion_id=meeting.id,
                usuario_id=uid,
                estado_respuesta="Pendiente",
            )
        )
    db.session.flush()
    if added_ids:
        _append_history(meeting, "participant_added", previous_status=meeting.estado)
    if removed_ids:
        _append_history(meeting, "participant_removed", previous_status=meeting.estado)


def create_meeting(payload: dict) -> Reunion:
    actor = g.current_user
    _validate_actor_scope(actor)
    required = (
        "titulo",
        "motivo",
        "zona_id",
        "fecha",
        "hora_inicio",
        "hora_fin",
        "participant_ids",
        "responsable_reunion_id",
    )
    missing = [field for field in required if field not in payload or payload.get(field) in (None, "", [])]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")
    participant_ids = [int(value) for value in payload.get("participant_ids", [])]
    participants = _validate_participants(participant_ids)
    responsable = _validate_responsable(int(payload["responsable_reunion_id"]), participants, actor)

    if actor.role.nombre == ROLE_AGENDADOR:
        for participant in participants:
            if participant.area_id != actor.area_id:
                raise ForbiddenError("El Agendador de área solo puede invitar a personas de su área.")

    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()
    _validate_basic_schedule(fecha, hora_inicio, hora_fin)
    zone = _find_zone(int(payload["zona_id"]))
    
    if actor.role.nombre == ROLE_AGENDADOR and zone.area_id not in (actor.area_id, None):
        raise ForbiddenError("El Agendador de área solo puede crear reuniones en zonas de su área o zonas globales.")
        
    _validate_zone_conflicts(zone, fecha, hora_inicio, hora_fin)
    participant_conflict_ids = list({responsable.id, *participant_ids})
    _validate_person_conflicts(participant_conflict_ids, fecha, hora_inicio, hora_fin)

    meeting = Reunion(
        titulo=payload["titulo"].strip(),
        motivo=payload["motivo"].strip(),
        creador_id=actor.id,
        responsable_reunion_id=responsable.id,
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
            "responsable_nombre": responsable.nombre,
            "zona_id": zone.id,
            "zona_nombre": zone.nombre,
            "meeting_title": meeting.titulo,
            "meeting_fecha": meeting.fecha.strftime("%d/%m/%Y"),
            "meeting_hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
            "meeting_hora_fin": meeting.hora_fin.strftime("%H:%M"),
        },
    )
    queue_meeting_notifications(meeting, "meeting_created")
    queue_meeting_emails(meeting, "meeting_created")
    _append_history(meeting, "created", previous_status=None)
    db.session.commit()
    _dispatch_after_commit()
    return meeting


def update_meeting(meeting: Reunion, payload: dict) -> Reunion:
    actor = g.current_user
    if actor.role.nombre not in OPERATOR_ROLES:
        raise ForbiddenError("Solo el personal autorizado puede modificar reuniones.")
    if meeting.estado == "Cancelada":
        raise ValidationError("No se puede editar una reunion cancelada.")
    required = (
        "titulo",
        "motivo",
        "zona_id",
        "fecha",
        "hora_inicio",
        "hora_fin",
        "participant_ids",
        "responsable_reunion_id",
    )
    missing = [field for field in required if field not in payload or payload.get(field) in (None, "", [])]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")

    participant_ids = [int(value) for value in payload.get("participant_ids", [])]
    participants = _validate_participants(participant_ids)
    responsable = _validate_responsable(int(payload["responsable_reunion_id"]), participants, actor)
    
    if actor.role.nombre == ROLE_AGENDADOR:
        for participant in participants:
            if participant.area_id != actor.area_id:
                raise ForbiddenError("El Agendador de área solo puede invitar a personas de su área.")
    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()
    _validate_basic_schedule(fecha, hora_inicio, hora_fin)
    zone = _find_zone(int(payload["zona_id"]))
    
    if actor.role.nombre == ROLE_AGENDADOR and zone.area_id not in (actor.area_id, None):
        raise ForbiddenError("El Agendador de área solo puede crear reuniones en zonas de su área o zonas globales.")
        
    _validate_zone_conflicts(zone, fecha, hora_inicio, hora_fin, meeting_id=meeting.id)
    participant_conflict_ids = list({responsable.id, *participant_ids})
    _validate_person_conflicts(
        participant_conflict_ids,
        fecha,
        hora_inicio,
        hora_fin,
        meeting_id=meeting.id,
    )

    previous_status = meeting.estado
    meeting.titulo = payload["titulo"].strip()
    meeting.motivo = payload["motivo"].strip()
    meeting.responsable_reunion_id = responsable.id
    meeting.zona_id = zone.id
    meeting.fecha = fecha
    meeting.hora_inicio = hora_inicio
    meeting.hora_fin = hora_fin
    meeting.prioridad = payload.get("prioridad", meeting.prioridad)
    
    sync_meeting_participants(meeting, participant_ids)
    log_event(
        "modificacion_reunion",
        "reunion",
        "exitoso",
        entity_id=meeting.id,
        detail={"meeting_title": meeting.titulo, "responsable_nombre": responsable.nombre},
    )
    queue_meeting_notifications(meeting, "meeting_updated")
    queue_meeting_emails(meeting, "meeting_updated")
    _append_history(meeting, "updated", previous_status=previous_status)
    db.session.commit()
    _dispatch_after_commit()
    return meeting


def cancel_meeting(meeting: Reunion) -> Reunion:
    actor = g.current_user
    if actor.role.nombre not in OPERATOR_ROLES:
        raise ForbiddenError("Solo el personal autorizado puede cancelar reuniones.")
    previous_status = meeting.estado
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
    queue_meeting_emails(meeting, "meeting_canceled")
    _append_history(meeting, "canceled", previous_status=previous_status)
    db.session.commit()
    _dispatch_after_commit()
    return meeting


def respond_to_meeting(meeting: Reunion, *, accept: bool, reason: str | None = None) -> ReunionParticipante:
    actor = g.current_user
    item = next((row for row in meeting.participantes if row.usuario_id == actor.id), None)
    if not item and meeting.responsable_reunion_id != actor.id:
        raise ForbiddenError("No participa en esta reunion.")
    if meeting.estado == "Cancelada":
        raise ValidationError("No puede responder una reunion cancelada.")
    if not item:
        item = ReunionParticipante(
            reunion_id=meeting.id,
            usuario_id=actor.id,
            estado_respuesta="Pendiente",
        )
        db.session.add(item)
        db.session.flush()
    if accept:
        item.estado_respuesta = "Aceptada"
        item.razon_rechazo = None
        action = "aceptacion_reunion"
        response_status = "Aceptada"
    else:
        if not reason or not reason.strip():
            raise ValidationError("Debe indicar una razon de rechazo.")
        item.estado_respuesta = "Rechazada"
        item.razon_rechazo = reason.strip()
        action = "rechazo_reunion"
        response_status = "Rechazada"
    item.fecha_respuesta = datetime.utcnow()
    previous_status = meeting.estado
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
    queue_meeting_notifications(
        meeting,
        "meeting_response",
        {
            "responder_nombre": actor.nombre,
            "response_status": response_status,
            "response_reason": item.razon_rechazo,
        },
    )
    queue_meeting_emails(
        meeting,
        "meeting_response",
        {
            "responder_nombre": actor.nombre,
            "response_status": response_status,
            "response_reason": item.razon_rechazo,
        },
    )
    _append_history(meeting, "response", previous_status=previous_status)
    db.session.commit()
    _dispatch_after_commit()
    return item


def _append_history(meeting: Reunion, event_type: str, previous_status: str | None) -> None:
    actor = getattr(g, "current_user", None)
    history = ReunionHistorial(
        reunion_id=meeting.id,
        actor_usuario_id=getattr(actor, "id", None),
        tipo_evento=event_type,
        estado_anterior=previous_status,
        estado_nuevo=meeting.estado,
        snapshot_json=json.dumps(serialize_meeting(meeting), ensure_ascii=True),
        changed_at=datetime.utcnow(),
    )
    db.session.add(history)


def _dispatch_after_commit() -> None:
    dispatch_due_communications(now=datetime.utcnow())
    db.session.commit()
