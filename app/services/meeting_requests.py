from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from flask import g
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Configuracion,
    Reunion,
    ReunionParticipante,
    ReunionSolicitud,
    ReunionSolicitudParticipante,
    Usuario,
    ZonaReunion,
    Area,
    ReunionHistorial,
)
from app.errors import ValidationError, ConflictError, ForbiddenError
from app.constants import ROLE_AGENDADOR, ROLE_COLABORADOR, ROLE_SECRETARIA, ROLE_ADMIN
from app.services.notifications import (
    queue_meeting_emails,
    queue_meeting_notifications,
    dispatch_due_communications,
)


def _config_int(key: str, default: int) -> int:
    setting = Configuracion.query.filter_by(clave=key).first()
    return int(setting.valor) if setting else default


def _combine(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock)


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def check_availability(
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
    zona_id: int | None = None,
    usuario_ids: list[int] | None = None,
) -> dict:
    start_dt = _combine(fecha, hora_inicio)
    end_dt = _combine(fecha, hora_fin)

    # 1. Zonas
    global_margin = _config_int("margen_zona_minutos", 5)
    zones_status = []
    
    if zona_id is not None:
        active_zones = ZonaReunion.query.filter_by(id=zona_id, estado="Activa").all()
    else:
        active_zones = ZonaReunion.query.filter_by(estado="Activa").order_by(ZonaReunion.nombre).all()

    for zone in active_zones:
        margin = max(zone.margen_operativo_minutos, global_margin)
        meetings = Reunion.query.filter(
            Reunion.zona_id == zone.id,
            Reunion.fecha == fecha,
            Reunion.estado != "Cancelada",
        ).all()

        is_available = True
        motivo = None

        for meeting in meetings:
            other_start = _combine(meeting.fecha, meeting.hora_inicio) - timedelta(minutes=margin)
            other_end = _combine(meeting.fecha, meeting.hora_fin) + timedelta(minutes=margin)
            if _overlaps(start_dt, end_dt, other_start, other_end):
                is_available = False
                motivo = "Sala ocupada en ese horario"
                break

        zones_status.append(
            {
                "id": zone.id,
                "nombre": zone.nombre,
                "ubicacion": zone.ubicacion,
                "capacidad": zone.capacidad,
                "disponible": is_available,
                "motivo": motivo,
            }
        )

    # 2. Usuarios
    rest_minutes = _config_int("descanso_persona_minutos", 10)
    users_status = []
    
    if usuario_ids is not None:
        active_users = Usuario.query.filter(Usuario.id.in_(usuario_ids), Usuario.estado == "Activo").all()
    else:
        active_users = Usuario.query.filter_by(estado="Activo").order_by(Usuario.nombre).all()

    for user in active_users:
        is_available = True
        motivo = None

        # Check actual meetings
        meetings = (
            db.session.query(Reunion)
            .join(ReunionParticipante, Reunion.id == ReunionParticipante.reunion_id)
            .filter(
                ReunionParticipante.usuario_id == user.id,
                Reunion.fecha == fecha,
                Reunion.estado != "Cancelada",
            )
            .all()
        )

        for meeting in meetings:
            other_start = _combine(meeting.fecha, meeting.hora_inicio) - timedelta(minutes=rest_minutes)
            other_end = _combine(meeting.fecha, meeting.hora_fin) + timedelta(minutes=rest_minutes)
            if _overlaps(start_dt, end_dt, other_start, other_end):
                is_available = False
                motivo = "Este usuario ya posee una reunión"
                break

        # Check pending requests
        if is_available:
            solicitudes = (
                db.session.query(ReunionSolicitud)
                .join(
                    ReunionSolicitudParticipante,
                    ReunionSolicitud.id == ReunionSolicitudParticipante.solicitud_id,
                )
                .filter(
                    ReunionSolicitudParticipante.usuario_id == user.id,
                    ReunionSolicitud.fecha == fecha,
                    ReunionSolicitud.estado == "Pendiente",
                )
                .all()
            )
            for req in solicitudes:
                other_start = _combine(req.fecha, req.hora_inicio) - timedelta(minutes=rest_minutes)
                other_end = _combine(req.fecha, req.hora_fin) + timedelta(minutes=rest_minutes)
                if _overlaps(start_dt, end_dt, other_start, other_end):
                    is_available = False
                    motivo = "Este usuario no está disponible en el horario seleccionado (Solicitud pendiente)"
                    break

        users_status.append(
            {
                "id": user.id,
                "nombre": user.nombre,
                "correo": user.correo,
                "area_id": user.area_id,
                "area_nombre": user.area.nombre,
                "disponible": is_available,
                "motivo": motivo,
            }
        )

    return {
        "fecha": fecha.isoformat(),
        "hora_inicio": hora_inicio.strftime("%H:%M"),
        "hora_fin": hora_fin.strftime("%H:%M"),
        "zonas": zones_status,
        "usuarios": users_status,
    }


def create_meeting_request(payload: dict, actor: Usuario) -> ReunionSolicitud:
    if actor.role.nombre not in (ROLE_AGENDADOR, ROLE_COLABORADOR):
        raise ForbiddenError(
            "Solo Agendadores de área y Colaboradores pueden crear solicitudes de reunión."
        )

    required = ("titulo", "motivo", "zona_id", "fecha", "hora_inicio", "hora_fin", "participant_ids")
    missing = [
        field
        for field in required
        if field not in payload or payload.get(field) in (None, "", [])
    ]
    if missing:
        raise ValidationError(f"Faltan campos obligatorios: {', '.join(missing)}.")

    participant_ids = [int(v) for v in payload["participant_ids"]]
    if not participant_ids:
        raise ValidationError("Debe incluir al menos un participante.")

    if len(participant_ids) != len(set(participant_ids)):
        raise ValidationError("No se permiten participantes duplicados.")

    participants = Usuario.query.filter(Usuario.id.in_(participant_ids)).all()
    if len(participants) != len(participant_ids):
        raise ValidationError("Hay participantes inexistentes.")
    if any(p.estado != "Activo" for p in participants):
        raise ValidationError("Todos los participantes deben estar activos.")

    if actor.role.nombre == ROLE_AGENDADOR:
        for p in participants:
            if p.area_id != actor.area_id:
                raise ForbiddenError("El Agendador de área solo puede invitar a personas de su área.")

    fecha = date.fromisoformat(payload["fecha"])
    hora_inicio = datetime.strptime(payload["hora_inicio"], "%H:%M").time()
    hora_fin = datetime.strptime(payload["hora_fin"], "%H:%M").time()

    today = date.today()
    if fecha < today:
        raise ValidationError("La fecha no puede estar en el pasado.")
    if hora_fin <= hora_inicio:
        raise ValidationError("hora_fin debe ser mayor que hora_inicio.")

    duration = _combine(fecha, hora_fin) - _combine(fecha, hora_inicio)
    if duration < timedelta(minutes=15) or duration > timedelta(hours=8):
        raise ValidationError("La duracion debe estar entre 15 minutos y 8 horas.")

    zone = ZonaReunion.query.get(int(payload["zona_id"]))
    if not zone or zone.estado != "Activa":
        raise ValidationError("Zona de reunión no disponible o inactiva.")

    if actor.role.nombre == ROLE_AGENDADOR and zone.area_id not in (actor.area_id, None):
        raise ForbiddenError(
            "El Agendador de área solo puede crear solicitudes para zonas de su área o globales."
        )

    # Validate availability in real time
    availability = check_availability(fecha, hora_inicio, hora_fin)
    
    zone_avail = next((z for z in availability["zonas"] if z["id"] == zone.id), None)
    if not zone_avail or not zone_avail["disponible"]:
        raise ConflictError(
            f"La sala seleccionada no está disponible: {zone_avail['motivo'] if zone_avail else ''}"
        )

    for p_id in participant_ids:
        p_avail = next((u for u in availability["usuarios"] if u["id"] == p_id), None)
        if not p_avail or not p_avail["disponible"]:
            raise ConflictError(
                f"El participante {p_avail['nombre'] if p_avail else p_id} no está disponible: {p_avail['motivo'] if p_avail else ''}"
            )

    solicitud = ReunionSolicitud(
        solicitante_usuario_id=actor.id,
        titulo=payload["titulo"].strip(),
        motivo=payload["motivo"].strip(),
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        zona_id=zone.id,
        prioridad=payload.get("prioridad", "Media"),
        estado="Pendiente",
        observacion_solicitante=payload.get("observacion_solicitante", "").strip() or None,
    )
    db.session.add(solicitud)
    db.session.flush()

    for p in participants:
        sol_p = ReunionSolicitudParticipante(
            solicitud_id=solicitud.id,
            usuario_id=p.id,
            area_id=p.area_id,
        )
        db.session.add(sol_p)

    db.session.commit()
    return solicitud


def approve_meeting_request(request_id: int, actor: Usuario) -> Reunion:
    if actor.role.nombre not in (ROLE_SECRETARIA, ROLE_ADMIN):
        raise ForbiddenError(
            "Solo el personal de Secretaría o Administradores pueden aprobar solicitudes."
        )

    solicitud = ReunionSolicitud.query.get(request_id)
    if not solicitud:
        raise ValidationError("Solicitud de reunión no encontrada.")

    if solicitud.estado != "Pendiente":
        raise ValidationError(f"Esta solicitud ya no está pendiente (Estado: {solicitud.estado}).")

    if solicitud.solicitante_usuario_id == actor.id:
        raise ForbiddenError("No puede aprobar su propia solicitud de reunión.")

    availability = check_availability(solicitud.fecha, solicitud.hora_inicio, solicitud.hora_fin)
    
    zone_avail = next((z for z in availability["zonas"] if z["id"] == solicitud.zona_id), None)
    if not zone_avail or not zone_avail["disponible"]:
        raise ConflictError("La sala ya no está disponible en este horario.")

    participant_ids = [p.usuario_id for p in solicitud.participantes]
    for p_id in participant_ids:
        p_avail = next((u for u in availability["usuarios"] if u["id"] == p_id), None)
        if not p_avail or not p_avail["disponible"]:
            raise ConflictError(
                f"El participante {p_avail['nombre'] if p_avail else p_id} ya no está disponible en este horario."
            )

    # Determine responsable for the Reunion
    responsable_id = solicitud.solicitante_usuario_id
    if responsable_id not in participant_ids:
        # If the creator isn't a participant, set the first participant as responsable
        responsable_id = participant_ids[0]

    meeting = Reunion(
        titulo=solicitud.titulo,
        motivo=solicitud.motivo,
        creador_id=solicitud.solicitante_usuario_id,
        responsable_reunion_id=responsable_id,
        area_origen_id=solicitud.solicitante.area_id,
        zona_id=solicitud.zona_id,
        fecha=solicitud.fecha,
        hora_inicio=solicitud.hora_inicio,
        hora_fin=solicitud.hora_fin,
        estado="Pendiente",
        prioridad=solicitud.prioridad,
    )
    db.session.add(meeting)
    db.session.flush()

    for p_id in participant_ids:
        db.session.add(
            ReunionParticipante(
                reunion_id=meeting.id,
                usuario_id=p_id,
                estado_respuesta="Pendiente",
            )
        )

    # Update solicitud status
    solicitud.estado = "Aprobada"
    solicitud.reunion_id = meeting.id
    solicitud.revisada_por_usuario_id = actor.id
    solicitud.revisada_at = datetime.utcnow()

    # Append to meeting history
    history = ReunionHistorial(
        reunion_id=meeting.id,
        actor_usuario_id=actor.id,
        tipo_evento="created",
        estado_anterior=None,
        estado_nuevo=meeting.estado,
        snapshot_json=json.dumps(
            {
                "id": meeting.id,
                "titulo": meeting.titulo,
                "motivo": meeting.motivo,
                "creador_nombre": solicitud.solicitante.nombre,
                "responsable_reunion_nombre": meeting.responsable.nombre,
                "zona_nombre": meeting.zona.nombre,
                "fecha": meeting.fecha.isoformat(),
                "hora_inicio": meeting.hora_inicio.strftime("%H:%M"),
                "hora_fin": meeting.hora_fin.strftime("%H:%M"),
                "estado": meeting.estado,
            }
        ),
        changed_at=datetime.utcnow(),
    )
    db.session.add(history)

    queue_meeting_notifications(meeting, "meeting_created")
    queue_meeting_emails(meeting, "meeting_created")

    db.session.commit()
    dispatch_due_communications(now=datetime.utcnow())
    db.session.commit()

    return meeting


def reject_meeting_request(request_id: int, actor: Usuario, reason: str) -> ReunionSolicitud:
    if actor.role.nombre not in (ROLE_SECRETARIA, ROLE_ADMIN):
        raise ForbiddenError(
            "Solo el personal de Secretaría o Administradores pueden rechazar solicitudes."
        )

    solicitud = ReunionSolicitud.query.get(request_id)
    if not solicitud:
        raise ValidationError("Solicitud de reunión no encontrada.")

    if solicitud.estado != "Pendiente":
        raise ValidationError(f"Esta solicitud ya no está pendiente (Estado: {solicitud.estado}).")

    if not reason or not reason.strip():
        raise ValidationError("Debe proporcionar una razón para el rechazo.")

    solicitud.estado = "Rechazada"
    solicitud.respuesta_secretaria = reason.strip()
    solicitud.revisada_por_usuario_id = actor.id
    solicitud.revisada_at = datetime.utcnow()

    db.session.commit()
    return solicitud


def cancel_own_meeting_request(request_id: int, actor: Usuario) -> ReunionSolicitud:
    solicitud = ReunionSolicitud.query.get(request_id)
    if not solicitud:
        raise ValidationError("Solicitud de reunión no encontrada.")

    if solicitud.solicitante_usuario_id != actor.id:
        raise ForbiddenError("Solo el solicitante original puede cancelar esta solicitud.")

    if solicitud.estado != "Pendiente":
        raise ValidationError(f"No se puede cancelar una solicitud que ya está {solicitud.estado}.")

    solicitud.estado = "Cancelada"
    db.session.commit()
    return solicitud
