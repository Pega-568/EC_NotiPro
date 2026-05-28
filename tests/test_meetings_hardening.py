import pytest
from datetime import date, datetime, time

from app.constants import ROLE_ADMIN, ROLE_AGENDADOR, ROLE_SECRETARIA, ROLE_COLABORADOR
from app.errors import ForbiddenError, ValidationError
from app.models import Area, Role, Usuario, ZonaReunion, Reunion, ReunionParticipante
from app.services.meetings import create_meeting, update_meeting, sync_meeting_participants
from app.services.notifications import get_event_recipients


from app.extensions import db

@pytest.fixture
def base_data(app):
    with app.app_context():
        area1 = Area(nombre="Area 1", estado="Activa")
        area2 = Area(nombre="Area 2", estado="Activa")
        db.session.add_all([area1, area2])
        db.session.flush()

        role_admin = Role.query.filter_by(nombre=ROLE_ADMIN).first()
        role_agendador = Role.query.filter_by(nombre=ROLE_AGENDADOR).first()
        if not role_agendador:
            role_agendador = Role(nombre=ROLE_AGENDADOR)
            db.session.add(role_agendador)
            db.session.flush()
            
        role_secretaria = Role.query.filter_by(nombre=ROLE_SECRETARIA).first()
        role_colaborador = Role.query.filter_by(nombre=ROLE_COLABORADOR).first()

        u_admin = Usuario(nombre="Admin Test", correo="at@empresa.local", password_hash="1", role_id=role_admin.id, area_id=area1.id)
        u_agendador1 = Usuario(nombre="Agendador 1", correo="ag1@empresa.local", password_hash="1", role_id=role_agendador.id, area_id=area1.id)
        u_agendador2 = Usuario(nombre="Agendador 2", correo="ag2@empresa.local", password_hash="1", role_id=role_agendador.id, area_id=area2.id)
        u_colab1 = Usuario(nombre="Colab 1", correo="c1@empresa.local", password_hash="1", role_id=role_colaborador.id, area_id=area1.id)
        u_colab2 = Usuario(nombre="Colab 2", correo="c2@empresa.local", password_hash="1", role_id=role_colaborador.id, area_id=area2.id)
        
        db.session.add_all([u_admin, u_agendador1, u_agendador2, u_colab1, u_colab2])
        
        zona1 = ZonaReunion(nombre="Zona 1", ubicacion="U", capacidad=10, area_id=area1.id, estado="Activa")
        zona2 = ZonaReunion(nombre="Zona 2", ubicacion="U", capacidad=10, area_id=area2.id, estado="Activa")
        db.session.add_all([zona1, zona2])
        db.session.commit()
        
        return {
            "area1_id": area1.id, "area2_id": area2.id,
            "u_admin_id": u_admin.id, "u_agendador1_id": u_agendador1.id, "u_agendador2_id": u_agendador2.id,
            "u_colab1_id": u_colab1.id, "u_colab2_id": u_colab2.id,
            "zona1_id": zona1.id, "zona2_id": zona2.id
        }


def test_admin_cannot_create_meetings(app, base_data, monkeypatch):
    with app.app_context():
        admin = Usuario.query.get(base_data["u_admin_id"])
        class MockG:
            current_user = admin
        monkeypatch.setattr("app.services.meetings.g", MockG())

        payload = {
            "titulo": "Test", "motivo": "Test", "zona_id": base_data["zona1_id"],
            "fecha": "2030-01-01", "hora_inicio": "10:00", "hora_fin": "11:00",
            "participant_ids": [base_data["u_colab1_id"]],
            "responsable_reunion_id": base_data["u_colab1_id"]
        }
        with pytest.raises(ForbiddenError, match="No tiene permiso para crear o editar reuniones"):
            create_meeting(payload)


def test_agendador_area_restrictions(app, base_data, monkeypatch):
    with app.app_context():
        agendador = Usuario.query.get(base_data["u_agendador1_id"])
        class MockG:
            current_user = agendador
        monkeypatch.setattr("app.services.meetings.g", MockG())

        payload_wrong_user = {
            "titulo": "Test", "motivo": "Test", "zona_id": base_data["zona1_id"],
            "fecha": "2030-01-01", "hora_inicio": "10:00", "hora_fin": "11:00",
            "participant_ids": [base_data["u_colab1_id"], base_data["u_colab2_id"]],
            "responsable_reunion_id": base_data["u_colab1_id"]
        }
        with pytest.raises(ForbiddenError, match="El Agendador de área solo puede invitar a personas de su área."):
            create_meeting(payload_wrong_user)
                
        payload_wrong_zone = {
            "titulo": "Test", "motivo": "Test", "zona_id": base_data["zona2_id"],
            "fecha": "2030-01-01", "hora_inicio": "10:00", "hora_fin": "11:00",
            "participant_ids": [base_data["u_colab1_id"]],
            "responsable_reunion_id": base_data["u_colab1_id"]
        }
        with pytest.raises(ForbiddenError, match="El Agendador de área solo puede crear reuniones en zonas de su área o zonas globales."):
            create_meeting(payload_wrong_zone)


def test_responsable_must_be_in_participants(app, base_data, monkeypatch):
    with app.app_context():
        agendador = Usuario.query.get(base_data["u_agendador1_id"])
        class MockG:
            current_user = agendador
        monkeypatch.setattr("app.services.meetings.g", MockG())

        payload = {
            "titulo": "Test", "motivo": "Test", "zona_id": base_data["zona1_id"],
            "fecha": "2030-01-01", "hora_inicio": "10:00", "hora_fin": "11:00",
            "participant_ids": [base_data["u_colab1_id"]],
            "responsable_reunion_id": base_data["u_agendador1_id"]
        }
        with pytest.raises(ValidationError, match="El responsable de la reunión debe estar incluido en la lista de participantes."):
            create_meeting(payload)


def test_sync_meeting_participants_preserves_state(app, base_data):
    with app.app_context():
        u1 = Usuario.query.get(base_data["u_colab1_id"])
        u2 = Usuario.query.get(base_data["u_colab2_id"])
        u3 = Usuario.query.get(base_data["u_agendador1_id"])
        meeting = Reunion(
            titulo="T", motivo="M", creador_id=u3.id, responsable_reunion_id=u1.id,
            area_origen_id=base_data["area1_id"], zona_id=base_data["zona1_id"],
            fecha=date(2030, 1, 1), hora_inicio=time(10, 0), hora_fin=time(11, 0)
        )
        db.session.add(meeting)
        db.session.flush()
        
        p1 = ReunionParticipante(reunion_id=meeting.id, usuario_id=u1.id, estado_respuesta="Aceptada")
        p2 = ReunionParticipante(reunion_id=meeting.id, usuario_id=u2.id, estado_respuesta="Rechazada", razon_rechazo="No")
        db.session.add_all([p1, p2])
        db.session.commit()
        
        sync_meeting_participants(meeting, [u1.id, u3.id])
        db.session.commit()
        
        parts = {p.usuario_id: p for p in meeting.participantes}
        assert u2.id not in parts
        assert u1.id in parts
        assert parts[u1.id].estado_respuesta == "Aceptada"
        assert u3.id in parts
        assert parts[u3.id].estado_respuesta == "Pendiente"


def test_get_event_recipients(app, base_data):
    with app.app_context():
        u_creator = Usuario.query.get(base_data["u_agendador1_id"])
        u_resp = Usuario.query.get(base_data["u_agendador2_id"])
        u_p1 = Usuario.query.get(base_data["u_colab1_id"])
        u_p2 = Usuario.query.get(base_data["u_colab2_id"])
        
        meeting = Reunion(
            titulo="T", motivo="M", creador_id=u_creator.id, responsable_reunion_id=u_resp.id,
            area_origen_id=base_data["area1_id"], zona_id=base_data["zona1_id"],
            fecha=date(2030, 1, 1), hora_inicio=time(10, 0), hora_fin=time(11, 0)
        )
        db.session.add(meeting)
        db.session.flush()
        
        p1 = ReunionParticipante(reunion_id=meeting.id, usuario_id=u_p1.id, estado_respuesta="Aceptada")
        p2 = ReunionParticipante(reunion_id=meeting.id, usuario_id=u_p2.id, estado_respuesta="Rechazada")
        db.session.add_all([p1, p2])
        db.session.commit()
        
        recips = get_event_recipients(meeting, "meeting_response")
        ids = {u.id for u in recips}
        assert ids == {u_creator.id, u_resp.id}
        
        recips = get_event_recipients(meeting, "reminder_30")
        ids = {u.id for u in recips}
        assert ids == {u_creator.id, u_resp.id, u_p1.id}
        assert u_p2.id not in ids
        
        recips = get_event_recipients(meeting, "meeting_updated")
        ids = {u.id for u in recips}
        assert ids == {u_creator.id, u_resp.id, u_p1.id, u_p2.id}
