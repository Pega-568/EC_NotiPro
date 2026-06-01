from datetime import date, timedelta

import pytest

from app import create_app
from app.constants import ROLE_ADMIN, ROLE_COLABORADOR, ROLE_SECRETARIA
from app.extensions import db
from app.models import Area, Configuracion, DeviceToken, NotificationEvent, NotificationLog, Reunion, ReunionParticipante, Role, Usuario, ZonaReunion
from app.security import hash_password


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin_role = Role(nombre=ROLE_ADMIN)
        scheduler_role = Role(nombre=ROLE_SECRETARIA)
        user_role = Role(nombre=ROLE_COLABORADOR)
        db.session.add_all([admin_role, scheduler_role, user_role])
        conta = Area(nombre="Contabilidad", estado="Activa")
        mercado = Area(nombre="Mercado Privado", estado="Activa")
        db.session.add_all([conta, mercado])
        db.session.flush()
        users = [
            Usuario(
                nombre="Admin",
                correo="admin@empresa.local",
                telefono="0990000001",
                password_hash=hash_password("Admin123!"),
                role_id=admin_role.id,
                area_id=conta.id,
            ),
            Usuario(
                nombre="Secretaria",
                correo="secretaria.general@empresa.local",
                telefono="0990000002",
                password_hash=hash_password("Agenda123!"),
                role_id=scheduler_role.id,
                area_id=conta.id,
            ),
            Usuario(
                nombre="Usuario 1",
                correo="usuario1.contabilidad@empresa.local",
                telefono="0990000003",
                password_hash=hash_password("Usuario123!"),
                role_id=user_role.id,
                area_id=conta.id,
            ),
            Usuario(
                nombre="Usuario 2",
                correo="usuario2.contabilidad@empresa.local",
                telefono="0990000004",
                password_hash=hash_password("Usuario123!"),
                role_id=user_role.id,
                area_id=conta.id,
            ),
            Usuario(
                nombre="Usuario Mercado",
                correo="usuario1.mercado@empresa.local",
                telefono="0990000005",
                password_hash=hash_password("Usuario123!"),
                role_id=user_role.id,
                area_id=mercado.id,
            ),
        ]
        db.session.add_all(users)
        zone1 = ZonaReunion(
            nombre="Sala Principal",
            ubicacion="Piso 1",
            capacidad=20,
            estado="Activa",
            margen_operativo_minutos=5,
        )
        zone2 = ZonaReunion(
            nombre="Sala Contabilidad",
            ubicacion="Piso 2",
            capacidad=8,
            estado="Activa",
            margen_operativo_minutos=5,
        )
        db.session.add_all([zone1, zone2])
        for key, value in {
            "descanso_persona_minutos": "10",
            "margen_zona_minutos": "5",
            "horario_laboral_inicio": "08:00",
            "horario_laboral_fin": "17:00",
            "max_intentos_login": "5",
            "debug_mode": "false",
            "recordatorio_30_minutos": "true",
            "recordatorio_10_minutos": "true",
        }.items():
            db.session.add(Configuracion(clave=key, valor=value))
        db.session.commit()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, correo, password):
    response = client.post("/api/auth/login", json={"correo": correo, "password": password})
    csrf = response.get_json()["csrf_token"]
    return {"X-CSRF-Token": csrf}
