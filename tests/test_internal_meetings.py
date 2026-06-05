from datetime import date, timedelta

from app.constants import ROLE_AGENDADOR
from app.extensions import db
from app.models import LogSistema, Reunion, Role, Usuario
from app.security import hash_password


def login(client, correo, password):
    response = client.post("/api/auth/login", json={"correo": correo, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}


def mobile_login(client, correo, password):
    response = client.post("/api/mobile/auth/login", json={"correo": correo, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def ensure_agendador(app):
    with app.app_context():
        role = Role.query.filter_by(nombre=ROLE_AGENDADOR).first()
        if not role:
            role = Role(nombre=ROLE_AGENDADOR)
            db.session.add(role)
            db.session.flush()
        user = Usuario.query.filter_by(correo="encargado.interno@empresa.local").first()
        if not user:
            user = Usuario(
                nombre="Encargado Interno",
                correo="encargado.interno@empresa.local",
                telefono="0990000010",
                password_hash=hash_password("Encargado123!"),
                role_id=role.id,
                area_id=1,
            )
            db.session.add(user)
            db.session.commit()


def _future_day(offset=2):
    return (date.today() + timedelta(days=offset)).isoformat()


def _payload(participant_ids, *, day=2, zone_id=2, start="09:00", end="10:00", responsible_id=None):
    return {
        "titulo": "Interna de area",
        "motivo": "Seguimiento interno",
        "zona_id": zone_id,
        "fecha": _future_day(day),
        "hora_inicio": start,
        "hora_fin": end,
        "prioridad": "Alta",
        "participant_ids": participant_ids,
        "responsable_reunion_id": responsible_id or participant_ids[0],
    }


def test_encargado_crea_reunion_interna_con_participantes_de_su_area(client, app):
    ensure_agendador(app)
    headers = login(client, "encargado.interno@empresa.local", "Encargado123!")

    response = client.post("/api/reuniones-internas", json=_payload([3, 4]), headers=headers)

    assert response.status_code == 201
    body = response.get_json()
    assert body["prioridad"] == "Baja"
    assert body["estado"] == "Pendiente"
    assert {item["usuario_id"] for item in body["participantes"]} == {3, 4}


def test_encargado_no_puede_incluir_participantes_de_otra_area(client, app):
    ensure_agendador(app)
    headers = login(client, "encargado.interno@empresa.local", "Encargado123!")

    response = client.post(
        "/api/reuniones-internas",
        json=_payload([3, 5], responsible_id=3),
        headers=headers,
    )

    assert response.status_code == 403
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="rechazo_reunion_interna").order_by(LogSistema.id.desc()).first()
        assert entry is not None
        assert "participante_otra_area" in (entry.detalle_seguro or "")


def test_colaborador_no_puede_crear_reunion_interna(client, app):
    headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")

    response = client.post("/api/reuniones-internas", json=_payload([3, 4]), headers=headers)

    assert response.status_code == 403
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="rechazo_reunion_interna").order_by(LogSistema.id.desc()).first()
        assert entry is not None
        assert "usuario_sin_permiso" in (entry.detalle_seguro or "")


def test_admin_puede_crear_reunion_interna(client):
    headers = login(client, "admin@empresa.local", "Admin123!")

    response = client.post("/api/reuniones-internas", json=_payload([3, 5], zone_id=1), headers=headers)

    assert response.status_code == 201
    assert response.get_json()["creador_nombre"] == "Admin"


def test_secretaria_puede_crear_reunion_interna(client):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")

    response = client.post("/api/reuniones-internas", json=_payload([3, 5], day=3, zone_id=1), headers=headers)

    assert response.status_code == 201
    assert response.get_json()["creador_nombre"] == "Secretaria"


def test_prioridad_alta_en_payload_termina_guardada_como_baja(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")

    response = client.post("/api/reuniones-internas", json=_payload([3], day=4), headers=headers)

    assert response.status_code == 201
    meeting_id = response.get_json()["id"]
    with app.app_context():
        assert Reunion.query.get(meeting_id).prioridad == "Baja"


def test_conflicto_de_sala_bloquea_reunion_interna(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    payload = _payload([3], day=5, zone_id=1)
    assert client.post("/api/reuniones-internas", json=payload, headers=headers).status_code == 201

    response = client.post(
        "/api/reuniones-internas",
        json=_payload([4], day=5, zone_id=1, start="09:30", end="10:30"),
        headers=headers,
    )

    assert response.status_code == 409
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="rechazo_reunion_interna").order_by(LogSistema.id.desc()).first()
        assert "conflicto_sala" in (entry.detalle_seguro or "")


def test_conflicto_de_participante_bloquea_reunion_interna(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    assert client.post(
        "/api/reuniones-internas",
        json=_payload([3], day=6, zone_id=1),
        headers=headers,
    ).status_code == 201

    response = client.post(
        "/api/reuniones-internas",
        json=_payload([3], day=6, zone_id=2, start="09:30", end="10:30"),
        headers=headers,
    )

    assert response.status_code == 409
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="rechazo_reunion_interna").order_by(LogSistema.id.desc()).first()
        assert "conflicto_participante" in (entry.detalle_seguro or "")


def test_reunion_interna_aparece_en_mobile_sync_para_participante(client):
    web_headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    created = client.post(
        "/api/reuniones-internas",
        json=_payload([3], day=7, zone_id=1),
        headers=web_headers,
    ).get_json()

    mobile_headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/sync", headers=mobile_headers)

    assert response.status_code == 200
    ids = {item["id"] for item in response.get_json()["reuniones"]}
    assert created["id"] in ids


def test_secretaria_puede_ver_reunion_interna_creada(client):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post(
        "/api/reuniones-internas",
        json=_payload([3], day=8, zone_id=1),
        headers=admin_headers,
    ).get_json()

    secretaria_headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    response = client.get("/api/reuniones", headers=secretaria_headers)

    assert response.status_code == 200
    assert created["id"] in {item["id"] for item in response.get_json()["items"]}


def test_auditoria_registra_creacion_de_reunion_interna(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    created = client.post(
        "/api/reuniones-internas",
        json=_payload([3], day=9, zone_id=1),
        headers=headers,
    ).get_json()

    with app.app_context():
        entry = LogSistema.query.filter_by(accion="creacion_reunion_interna").order_by(LogSistema.id.desc()).first()
        assert entry is not None
        assert entry.entidad_id == str(created["id"])
        assert "Interna de area" in entry.descripcion_humana


def test_mobile_endpoint_devuelve_payload_movil(client):
    headers = mobile_login(client, "secretaria.general@empresa.local", "Agenda123!")

    response = client.post(
        "/api/mobile/reuniones-internas",
        json=_payload([3], day=10, zone_id=1),
        headers=headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "zona" in body
    assert "creador" in body
    assert body["prioridad"] == "Baja"
