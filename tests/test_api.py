from datetime import date, timedelta

from app.models import Area, LogSistema, NotificationEvent, Reunion, Usuario, ZonaReunion


def login(client, correo, password):
    response = client.post("/api/auth/login", json={"correo": correo, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}


def _future_day():
    return (date.today() + timedelta(days=1)).isoformat()


def _meeting_payload(participant_ids, zone_id=1, start="09:00", end="10:00", responsible_id=None):
    return {
        "titulo": "Comite operativo",
        "motivo": "Revision semanal",
        "zona_id": zone_id,
        "fecha": _future_day(),
        "hora_inicio": start,
        "hora_fin": end,
        "prioridad": "Alta",
        "participant_ids": participant_ids,
        "responsable_reunion_id": responsible_id or participant_ids[0],
    }


def test_admin_crea_area(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/areas", json={"nombre": "Gerencia"}, headers=headers)
    assert response.status_code == 201
    assert response.get_json()["nombre"] == "Gerencia"


def test_admin_crea_usuario(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post(
        "/api/usuarios",
        json={
            "nombre": "Usuario Nuevo",
            "correo": "nuevo@empresa.local",
            "password": "Segura123!",
            "role_id": 3,
            "area_id": 1,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert "password_hash" not in response.get_data(as_text=True)


def test_admin_crea_zona(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post(
        "/api/zonas",
        json={"nombre": "Sala Gerencia", "ubicacion": "Piso 4", "capacidad": 6},
        headers=headers,
    )
    assert response.status_code == 201


def test_admin_crea_reunion_multiarea(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/reuniones", json=_meeting_payload([3, 5]), headers=headers)
    assert response.status_code == 201
    assert response.get_json()["estado"] == "Pendiente"


def test_agendador_crea_reunion_misma_area(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    response = client.post("/api/reuniones", json=_meeting_payload([3, 4], zone_id=2), headers=headers)
    assert response.status_code == 201


def test_secretaria_puede_convocar_otra_area(client, app):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    response = client.post("/api/reuniones", json=_meeting_payload([3, 5], zone_id=2), headers=headers)
    assert response.status_code == 201


def test_usuario_natural_no_puede_crear_reunion(client, app):
    headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post("/api/reuniones", json=_meeting_payload([4], zone_id=2), headers=headers)
    assert response.status_code == 403


def test_usuario_natural_ve_solo_sus_reuniones(client, app):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    client.post("/api/reuniones", json=_meeting_payload([4], start="10:30", end="11:30"), headers=admin_headers)
    user_headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/reuniones", headers=user_headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


def test_usuario_natural_acepta_reunion(client, app):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    user_headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post(f"/api/reuniones/{created['id']}/aceptar", headers=user_headers)
    assert response.status_code == 200
    assert response.get_json()["participantes"][0]["estado_respuesta"] == "Aceptada"


def test_usuario_natural_rechaza_con_razon(client, app):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    user_headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post(
        f"/api/reuniones/{created['id']}/rechazar",
        json={"razon": "Cruce de agenda"},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["estado"] == "Rechazada"


def test_usuario_natural_no_rechaza_vacio(client, app):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    user_headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.post(f"/api/reuniones/{created['id']}/rechazar", json={"razon": ""}, headers=user_headers)
    assert response.status_code == 422


def test_persona_no_puede_doble_horario(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    first = client.post("/api/reuniones", json=_meeting_payload([3]), headers=headers)
    assert first.status_code == 201
    second = client.post("/api/reuniones", json=_meeting_payload([3], start="09:30", end="10:30"), headers=headers)
    assert second.status_code == 409


def test_zona_no_puede_doble_horario(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    first = client.post("/api/reuniones", json=_meeting_payload([3], zone_id=1), headers=headers)
    assert first.status_code == 201
    second = client.post("/api/reuniones", json=_meeting_payload([4], zone_id=1, start="09:30", end="10:30"), headers=headers)
    assert second.status_code == 409


def test_intento_no_autorizado_queda_en_logs(client, app):
    headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/logs", headers=headers)
    assert response.status_code == 403
    with app.app_context():
        assert LogSistema.query.filter_by(accion="intento_no_autorizado").count() >= 1
        entry = LogSistema.query.filter_by(accion="intento_no_autorizado").order_by(LogSistema.id.desc()).first()
        assert entry.descripcion_humana


def test_password_hash_no_aparece_en_json(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.get("/api/usuarios", headers=headers)
    assert "password_hash" not in response.get_data(as_text=True)


def test_error_publico_no_filtra_stack_ni_sql(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/reuniones", json={"titulo": "sin datos"}, headers=headers)
    body = response.get_data(as_text=True).lower()
    assert response.status_code in (422, 500)
    assert "traceback" not in body
    assert "sqlalchemy" not in body


def test_logs_muestran_descripcion_humana(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    client.post("/api/areas", json={"nombre": "Gerencia"}, headers=headers)
    response = client.get("/api/logs", headers=headers)
    assert response.status_code == 200
    first_matching = next(item for item in response.get_json()["items"] if item["accion"] == "creacion_area")
    assert first_matching["descripcion_humana"]


def test_creacion_reunion_genera_log_humano(client, app):
    headers = login(client, "admin@empresa.local", "Admin123!")
    client.post("/api/reuniones", json=_meeting_payload([3, 5]), headers=headers)
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="creacion_reunion").order_by(LogSistema.id.desc()).first()
        assert "Comite operativo" in entry.descripcion_humana
        assert "Sala Principal" in entry.descripcion_humana
        events = NotificationEvent.query.filter_by(reunion_id=1).all()
        assert len(events) >= 3


def test_rechazo_reunion_genera_log_humano_con_razon(client, app):
    admin_headers = login(client, "admin@empresa.local", "Admin123!")
    created = client.post("/api/reuniones", json=_meeting_payload([3]), headers=admin_headers).get_json()
    user_headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    client.post(
        f"/api/reuniones/{created['id']}/rechazar",
        json={"razon": "Tengo atencion previamente asignada"},
        headers=user_headers,
    )
    with app.app_context():
        entry = LogSistema.query.filter_by(accion="rechazo_reunion").order_by(LogSistema.id.desc()).first()
        assert "Tengo atencion previamente asignada" in entry.descripcion_humana


def test_admin_puede_buscar_usuarios_por_area(client):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.get("/api/usuarios/buscar?area_id=1&q=usuario", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert any(item["correo"] == "usuario1.contabilidad@empresa.local" for item in payload)


def test_secretaria_puede_buscar_todas_las_areas(client):
    headers = login(client, "secretaria.general@empresa.local", "Agenda123!")
    response = client.get("/api/usuarios/buscar?area_id=2&q=usuario", headers=headers)
    assert response.status_code == 200


def test_usuario_natural_no_puede_buscar_usuarios(client):
    headers = login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/api/usuarios/buscar?area_id=1&q=usuario", headers=headers)
    assert response.status_code == 403


def test_backend_rechaza_participantes_duplicados(client):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/reuniones", json=_meeting_payload([3, 3]), headers=headers)
    assert response.status_code == 422


def test_backend_rechaza_participante_inexistente(client):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/reuniones", json=_meeting_payload([999]), headers=headers)
    assert response.status_code == 422


def test_backend_exige_responsable_reunion(client):
    headers = login(client, "admin@empresa.local", "Admin123!")
    payload = _meeting_payload([3, 4])
    payload.pop("responsable_reunion_id")
    response = client.post("/api/reuniones", json=payload, headers=headers)
    assert response.status_code == 422


def test_responsable_se_serializa_y_genera_historial(client):
    headers = login(client, "admin@empresa.local", "Admin123!")
    response = client.post("/api/reuniones", json=_meeting_payload([3, 4], responsible_id=4), headers=headers)
    meeting = response.get_json()
    assert meeting["responsable_reunion_id"] == 4
    history = client.get(f"/api/reuniones/{meeting['id']}/historial", headers=headers)
    assert history.status_code == 200
    assert history.get_json()["items"][0]["tipo_evento"] == "created"
