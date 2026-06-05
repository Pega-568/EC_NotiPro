from __future__ import annotations

from datetime import date, datetime

from flask import g

from app.audit import log_event
from app.constants import ROLE_ADMIN, ROLE_AGENDADOR, ROLE_SECRETARIA
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.extensions import db
from app.models import Reunion, ReunionParticipante, Usuario
from app.services.meetings import (
    _append_history,
    _dispatch_after_commit,
    _find_zone,
    _validate_basic_schedule,
    _validate_participants,
    _validate_person_conflicts,
    _validate_responsable,
    _validate_zone_conflicts,
)
from app.services.notifications import queue_meeting_emails, queue_meeting_notifications


ALLOWED_INTERNAL_MEETING_ROLES = (ROLE_ADMIN, ROLE_SECRETARIA, ROLE_AGENDADOR)


def _audit_rejection(
    *,
    actor: Usuario,
    reason: str,
    origin: str,
    detail: dict | None = None,
) -> None:
    g.current_user = actor
    payload = {"motivo": reason, "origen": origin}
    if detail:
        payload.update(detail)
    log_event(
        "rechazo_reunion_interna",
        "reunion_interna",
        "rechazado",
        detail=payload,
    )
    db.session.commit()


def _audit_success(meeting: Reunion, participant_ids: list[int], origin: str) -> None:
    log_event(
        "creacion_reunion_interna",
        "reunion_interna",
        "exitoso",
        entity_id=meeting.id,
        detail={
            "origen": origin,
            "participantes": participant_ids,
            "participant_names": [item.usuario.nombre for item in meeting.participantes],
            "zona_id": meeting.zona_id,
            "zona_nombre": meeting.zona.nombre,
            "meeting_title": meeting.titulo,
            "meeting_fecha": meeting.fecha.strftime("%d/%m/%Y"),
            "meeting_hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
            "meeting_hora_fin": meeting.hora_fin.strftime("%H:%M"),
        },
    )


def create_internal_area_meeting(actor: Usuario, payload: dict, origin: str) -> Reunion:
    if actor.role.nombre not in ALLOWED_INTERNAL_MEETING_ROLES:
        _audit_rejection(actor=actor, reason="usuario_sin_permiso", origin=origin)
        raise ForbiddenError("No tiene permiso para crear reuniones internas directas.")

    required = ("fecha", "hora_inicio", "hora_fin", "zona_id", "participant_ids")
    missing = [
        field
        for field in required
        if field not in payload or payload.get(field) in (None, "", [])
    ]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")

    participant_ids = [int(value) for value in payload.get("participant_ids", [])]
    participants = _validate_participants(participant_ids)
    responsable = _validate_responsable(
        int(payload.get("responsable_reunion_id") or participant_ids[0]),
        participants,
        actor,
    )

    if actor.role.nombre == ROLE_AGENDADOR:
        foreign_area_ids = sorted(
            {participant.area_id for participant in participants if participant.area_id != actor.area_id}
        )
        if foreign_area_ids:
            _audit_rejection(
                actor=actor,
                reason="participante_otra_area",
                origin=origin,
                detail={"areas_participantes": foreign_area_ids},
            )
            raise ForbiddenError(
                "El Encargado de Area solo puede crear reuniones internas con participantes de su area."
            )

    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()
    _validate_basic_schedule(fecha, hora_inicio, hora_fin)
    zone = _find_zone(int(payload["zona_id"]))

    if actor.role.nombre == ROLE_AGENDADOR and zone.area_id not in (actor.area_id, None):
        _audit_rejection(actor=actor, reason="zona_otra_area", origin=origin, detail={"zona_id": zone.id})
        raise ForbiddenError(
            "El Encargado de Area solo puede crear reuniones internas en zonas de su area o zonas globales."
        )

    try:
        _validate_zone_conflicts(zone, fecha, hora_inicio, hora_fin)
    except ConflictError:
        _audit_rejection(actor=actor, reason="conflicto_sala", origin=origin, detail={"zona_id": zone.id})
        raise

    try:
        _validate_person_conflicts(list({responsable.id, *participant_ids}), fecha, hora_inicio, hora_fin)
    except ConflictError:
        _audit_rejection(
            actor=actor,
            reason="conflicto_participante",
            origin=origin,
            detail={"participantes": participant_ids},
        )
        raise

    # TODO: Diferenciar temporalmente una reunion interna por auditoria/origen y prioridad Baja.
    # Si la UI necesita filtros especificos, agregar campos tipo_reunion/origen/requiere_aprobacion
    # con migracion para no inferir el tipo desde logs.
    meeting = Reunion(
        titulo=(payload.get("titulo") or "Reunion interna de area").strip(),
        motivo=(payload.get("motivo") or "Reunion interna directa de area").strip(),
        creador_id=actor.id,
        responsable_reunion_id=responsable.id,
        area_origen_id=actor.area_id,
        zona_id=zone.id,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        estado="Pendiente",
        prioridad="Baja",
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
    db.session.flush()

    g.current_user = actor
    _audit_success(meeting, participant_ids, origin)
    queue_meeting_notifications(meeting, "meeting_created")
    queue_meeting_emails(meeting, "meeting_created")
    _append_history(meeting, "created", previous_status=None)
    db.session.commit()
    _dispatch_after_commit()
    return meeting
