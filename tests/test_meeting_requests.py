import pytest
from datetime import date, time, timedelta
from app.extensions import db
from app.models import Usuario, ZonaReunion, ReunionSolicitud, ReunionSolicitudParticipante, Reunion
from app.constants import ROLE_COLABORADOR, ROLE_AGENDADOR, ROLE_SECRETARIA, ROLE_ADMIN
from app.services.meeting_requests import (
    check_availability,
    create_meeting_request,
    approve_meeting_request,
    reject_meeting_request,
    cancel_own_meeting_request,
)
from app.errors import ValidationError, ConflictError, ForbiddenError
from app.services.meetings import create_meeting


def test_colaborador_puede_crear_solicitud(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        zona = ZonaReunion.query.first()
        participantes = [Usuario.query.filter(Usuario.nombre == "Usuario 2").first()]

        payload = {
            "titulo": "Solicitud de Colaborador",
            "motivo": "Motivo de prueba",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [p.id for p in participantes],
            "observacion_solicitante": "Sin observaciones",
        }

        solicitud = create_meeting_request(payload, colaborador)
        assert solicitud.id is not None
        assert solicitud.estado == "Pendiente"
        assert solicitud.titulo == "Solicitud de Colaborador"
        assert len(solicitud.participantes) == 1


def test_agendador_puede_crear_solicitud(app):
    with app.app_context():
        from app.models import Role
        agendador_role = Role.query.filter(Role.nombre == ROLE_AGENDADOR).first()
        if not agendador_role:
            agendador_role = Role(nombre=ROLE_AGENDADOR)
            db.session.add(agendador_role)
            db.session.flush()

        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        agendador = Usuario(
            nombre="Agendador Test",
            correo="agendador.test@empresa.local",
            telefono="0990000009",
            password_hash="...",
            role_id=agendador_role.id,
            area_id=colaborador.area_id,
        )
        db.session.add(agendador)
        db.session.flush()

        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        payload = {
            "titulo": "Solicitud de Agendador",
            "motivo": "Motivo de prueba de agendador",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora_inicio": "11:00",
            "hora_fin": "12:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
        }

        solicitud = create_meeting_request(payload, agendador)
        assert solicitud.id is not None
        assert solicitud.estado == "Pendiente"


def test_colaborador_no_puede_crear_reunion_directa(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        payload = {
            "titulo": "Reunion Directa",
            "motivo": "Debe fallar",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
            "responsable_reunion_id": participante.id,
        }

        from flask import g
        g.current_user = colaborador
        with pytest.raises(ForbiddenError):
            create_meeting(payload)


def test_solicitud_no_crea_reunion_automaticamente(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        initial_reuniones = Reunion.query.count()

        payload = {
            "titulo": "Solicitud sin Reunion",
            "motivo": "Comprobar no creacion automatica",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora_inicio": "14:00",
            "hora_fin": "15:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
        }

        create_meeting_request(payload, colaborador)
        assert Reunion.query.count() == initial_reuniones


def test_secretaria_puede_ver_y_aprobar_solicitud(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        secretaria = Usuario.query.filter(Usuario.nombre == "Admin").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        payload = {
            "titulo": "Solicitud para Aprobar",
            "motivo": "Revisar flujo de aprobacion",
            "fecha": (date.today() + timedelta(days=3)).isoformat(),
            "hora_inicio": "09:00",
            "hora_fin": "10:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
        }

        solicitud = create_meeting_request(payload, colaborador)
        assert solicitud.estado == "Pendiente"

        reunion = approve_meeting_request(solicitud.id, secretaria)
        assert reunion.id is not None
        assert reunion.titulo == "Solicitud para Aprobar"
        assert solicitud.estado == "Aprobada"
        assert solicitud.reunion_id == reunion.id


def test_secretaria_puede_rechazar_solicitud(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        secretaria = Usuario.query.filter(Usuario.nombre == "Admin").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        payload = {
            "titulo": "Solicitud para Rechazar",
            "motivo": "Revisar flujo de rechazo",
            "fecha": (date.today() + timedelta(days=3)).isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
        }

        solicitud = create_meeting_request(payload, colaborador)
        assert solicitud.estado == "Pendiente"

        rechazada = reject_meeting_request(
            solicitud.id, secretaria, "Sala no disponible por reparaciones"
        )
        assert rechazada.estado == "Rechazada"
        assert rechazada.respuesta_secretaria == "Sala no disponible por reparaciones"
        assert rechazada.revisada_por_usuario_id == secretaria.id


def test_usuario_y_sala_ocupados_comprobacion_disponibilidad(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        secretaria = Usuario.query.filter(Usuario.nombre == "Admin").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        fecha = date.today() + timedelta(days=4)

        from flask import g
        g.current_user = secretaria

        meeting_payload = {
            "titulo": "Reunión Ocupante",
            "motivo": "Bloquear horario",
            "fecha": fecha.isoformat(),
            "hora_inicio": "14:00",
            "hora_fin": "15:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
            "responsable_reunion_id": participante.id,
        }
        create_meeting(meeting_payload)

        avail = check_availability(fecha, time(14, 0), time(15, 0))

        room_status = next(z for z in avail["zonas"] if z["id"] == zona.id)
        assert room_status["disponible"] is False
        assert room_status["motivo"] == "Sala ocupada en ese horario"

        user_status = next(u for u in avail["usuarios"] if u["id"] == participante.id)
        assert user_status["disponible"] is False
        assert user_status["motivo"] == "Este usuario ya posee una reunión"


def test_no_se_puede_aprobar_si_disponibilidad_cambio(app):
    with app.app_context():
        colaborador = Usuario.query.filter(Usuario.nombre == "Usuario 1").first()
        secretaria = Usuario.query.filter(Usuario.nombre == "Admin").first()
        zona = ZonaReunion.query.first()
        participante = Usuario.query.filter(Usuario.nombre == "Usuario 2").first()

        fecha = date.today() + timedelta(days=5)

        payload = {
            "titulo": "Solicitud A",
            "motivo": "Justificacion",
            "fecha": fecha.isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
        }
        solicitud = create_meeting_request(payload, colaborador)
        assert solicitud.estado == "Pendiente"

        from flask import g
        g.current_user = secretaria

        meeting_payload = {
            "titulo": "Reunión Ocupante Conflicto",
            "motivo": "Bloquear horario",
            "fecha": fecha.isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
            "responsable_reunion_id": participante.id,
        }
        create_meeting(meeting_payload)

        with pytest.raises(ConflictError):
            approve_meeting_request(solicitud.id, secretaria)
