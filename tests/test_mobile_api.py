from datetime import date, timedelta

from app.models import Usuario, ZonaReunion
from app.services.notifications import dispatch_pending_notifications
from app.services.meeting_requests import create_meeting_request


def mobile_login(client, correo, password):
    response = client.post("/api/mobile/auth/login", json={"correo": correo, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def _future_day():
    return (date.today() + timedelta(days=1)).isoformat()


def _meeting_payload(participant_ids, zone_id=1, start="09:00", end="10:00", responsible_id=None):
    return {
        "titulo": "Reunion movil",
        "motivo": "Seguimiento movil",
        "zona_id": zone_id,
        "fecha": _future_day(),
        "hora_inicio": start,
        "hora_fin": end,
        "prioridad": "Media",
        "participant_ids": participant_ids,
        "responsable_reunion_id": responsible_id or participant_ids[0],
    }


def api_login(client, correo, password):
    response = client.post("/api/auth/login", json={"correo": correo, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}


def test_mobile_login_y_me(client):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["user"]["correo"] == "usuario1.contabilidad@empresa.local"


def test_mobile_token_invalido_vuelve_401(client):
    response = client.get("/api/mobile/auth/me", headers={"Authorization": "Bearer invalido"})
    assert response.status_code == 401


def test_mobile_reuniones_lista_solo_propias(client):
    admin_headers = api_login(client, "secretaria.general@empresa.local", "Agenda123!")
    client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers)
    client.post("/api/reuniones", json=_meeting_payload([4], start="10:30", end="11:30"), headers=admin_headers)
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/reuniones", headers=headers)
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["mi_respuesta"] == "Pendiente"


def test_mobile_zonas_devuelve_contrato_minimo(client):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/zonas", headers=headers)
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items
    assert {"id", "nombre", "ubicacion", "capacidad"} == set(items[0])
    assert items[0]["capacidad"] > 0


def test_mobile_buscar_usuarios_devuelve_area_y_role(client):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/usuarios/buscar?q=usuario", headers=headers)
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items
    assert {"id", "nombre", "correo", "estado", "role", "area"} == set(items[0])
    assert {"id", "nombre"} == set(items[0]["area"])


def test_mobile_solicitudes_lista_propias(client, app):
    with app.app_context():
        solicitante = Usuario.query.filter_by(correo="usuario1.contabilidad@empresa.local").first()
        participante = Usuario.query.filter_by(correo="usuario2.contabilidad@empresa.local").first()
        zona = ZonaReunion.query.first()
        create_meeting_request(
            {
                "titulo": "Solicitud movil",
                "motivo": "Revision desde app movil",
                "fecha": (date.today() + timedelta(days=2)).isoformat(),
                "hora_inicio": "14:00",
                "hora_fin": "15:00",
                "zona_id": zona.id,
                "participant_ids": [participante.id],
            },
            solicitante,
        )

    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/solicitudes", headers=headers)
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["titulo"] == "Solicitud movil"
    assert items[0]["zona"]["capacidad"] > 0
    assert items[0]["solicitante"]["area"]["nombre"] == "Contabilidad"


def test_mobile_sync_devuelve_reuniones_y_solicitudes(client):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/mobile/sync", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"reuniones", "solicitudes", "server_time"}
    assert isinstance(payload["reuniones"], list)
    assert isinstance(payload["solicitudes"], list)
    assert payload["server_time"]


def test_mobile_detalle_aceptar_y_rechazar(client):
    admin_headers = api_login(client, "secretaria.general@empresa.local", "Agenda123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")

    detail = client.get(f"/api/mobile/reuniones/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.get_json()["titulo"] == "Reunion movil"

    accept = client.post(f"/api/mobile/reuniones/{created['id']}/aceptar", headers=headers)
    assert accept.status_code == 200
    assert accept.get_json()["mi_respuesta"] == "Aceptada"

    created2 = client.post(
        "/api/reuniones",
        json=_meeting_payload([3], start="12:30", end="13:30"),
        headers=admin_headers,
    ).get_json()
    reject = client.post(
        f"/api/mobile/reuniones/{created2['id']}/rechazar",
        headers=headers,
        json={"razon": "No podre asistir"},
    )
    assert reject.status_code == 200
    assert reject.get_json()["mi_respuesta"] == "Rechazada"


def test_mobile_rechazo_sin_razon_falla(client):
    admin_headers = api_login(client, "secretaria.general@empresa.local", "Agenda123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post(f"/api/mobile/reuniones/{created['id']}/rechazar", headers=headers, json={"razon": ""})
    assert response.status_code == 422


def test_mobile_logout_revoca_token(client):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    logout = client.post("/api/mobile/auth/logout", headers=headers)
    assert logout.status_code == 200
    me = client.get("/api/mobile/auth/me", headers=headers)
    assert me.status_code == 401


def test_mobile_registra_device_token(client, app):
    headers = mobile_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post(
        "/api/mobile/device-token",
        headers=headers,
        json={"token": "token-demo-001", "app_version": "0.1.0", "debug_ui": True},
    )
    assert response.status_code == 200
    with app.app_context():
        from app.models import DeviceToken

        device = DeviceToken.query.filter_by(token="token-demo-001").first()
        assert device is not None
        assert device.estado == "Activo"


def test_dispatch_notificaciones_sin_dispositivo_genera_logs(client, app):
    admin_headers = api_login(client, "secretaria.general@empresa.local", "Agenda123!")
    client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers)
    with app.app_context():
        from app.models import NotificationEvent, NotificationLog

        processed = dispatch_pending_notifications()
        db_event = NotificationEvent.query.filter_by(tipo_evento="meeting_created").first()
        logs = NotificationLog.query.filter_by(notification_event_id=db_event.id).all()

        assert processed >= 0
        assert db_event is not None
        assert db_event.estado == "Fallido"
        assert any(item.resultado == "usuario_sin_dispositivo" for item in logs)
