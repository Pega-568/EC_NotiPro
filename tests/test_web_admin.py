from datetime import date, timedelta

from app.models import Area, LogSistema, Reunion, Usuario


def future_day():
    return (date.today() + timedelta(days=1)).isoformat()


def web_login(client, correo="admin@empresa.local", password="Admin123!"):
    response = client.post(
        "/login",
        data={"correo": correo, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client.get_cookie("csrf_token").value


def test_favicon_no_devuelve_500(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 204


def test_admin_puede_ver_lista_usuarios(client):
    web_login(client)
    response = client.get("/web/admin/usuarios")
    assert response.status_code == 200
    assert "admin@empresa.local" in response.get_data(as_text=True)


def test_admin_puede_crear_usuario(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/usuarios/nuevo",
        data={
            "csrf_token": csrf,
            "nombre": "Web Nuevo",
            "correo": "web.nuevo@empresa.local",
            "telefono": "0991111111",
            "role_id": "3",
            "area_id": "1",
            "estado": "Activo",
            "password_temporal": "Temporal123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(correo="web.nuevo@empresa.local").first() is not None


def test_admin_puede_editar_usuario(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/usuarios/3/editar",
        data={
            "csrf_token": csrf,
            "nombre": "Usuario Uno Editado",
            "correo": "usuario1.contabilidad@empresa.local",
            "telefono": "0992222333",
            "role_id": "3",
            "area_id": "1",
            "estado": "Activo",
            "password_temporal": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Usuario.query.get(3).nombre == "Usuario Uno Editado"


def test_admin_puede_desactivar_usuario(client, app):
    csrf = web_login(client)
    response = client.post("/web/admin/usuarios/3/desactivar", data={"csrf_token": csrf}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Usuario.query.get(3).estado == "Inactivo"


def test_admin_puede_crear_area(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/areas/nueva",
        data={"csrf_token": csrf, "nombre": "Gerencia", "descripcion": "Area nueva", "estado": "Activa"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Area.query.filter_by(nombre="Gerencia").first() is not None


def test_admin_puede_crear_zona(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/zonas/nueva",
        data={
            "csrf_token": csrf,
            "nombre": "Sala Web",
            "ubicacion": "Piso 9",
            "capacidad": "12",
            "area_id": "1",
            "estado": "Activa",
            "margen_operativo_minutos": "5",
            "descripcion": "Sala creada desde web",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Sala Web" in response.get_data(as_text=True)


def test_admin_puede_crear_reunion_multiarea(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/reuniones/nueva",
        data={
            "csrf_token": csrf,
            "titulo": "Reunion Web",
            "motivo": "Revision interareas",
            "fecha": future_day(),
            "hora_inicio": "09:00",
            "hora_fin": "10:00",
            "zona_id": "1",
            "prioridad": "Alta",
            "participant_ids": ["3", "5"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Participantes" in response.get_data(as_text=True)
    with app.app_context():
        assert Reunion.query.filter_by(titulo="Reunion Web").first() is not None


def test_reunion_con_conflicto_se_rechaza(client):
    csrf = web_login(client)
    client.post(
        "/web/admin/reuniones/nueva",
        data={
            "csrf_token": csrf,
            "titulo": "Reunion Base",
            "motivo": "Base",
            "fecha": future_day(),
            "hora_inicio": "09:00",
            "hora_fin": "10:00",
            "zona_id": "1",
            "prioridad": "Alta",
            "participant_ids": ["3"],
        },
        follow_redirects=True,
    )
    response = client.post(
        "/web/admin/reuniones/nueva",
        data={
            "csrf_token": csrf,
            "titulo": "Reunion Conflicto",
            "motivo": "Cruce",
            "fecha": future_day(),
            "hora_inicio": "09:30",
            "hora_fin": "10:30",
            "zona_id": "1",
            "prioridad": "Alta",
            "participant_ids": ["3"],
        },
    )
    assert response.status_code == 200
    assert "conflicto" in response.get_data(as_text=True).lower() or "horario" in response.get_data(as_text=True).lower()


def test_admin_puede_cancelar_reunion(client, app):
    csrf = web_login(client)
    client.post(
        "/web/admin/reuniones/nueva",
        data={
            "csrf_token": csrf,
            "titulo": "Reunion Cancelable",
            "motivo": "Cancelar",
            "fecha": future_day(),
            "hora_inicio": "11:00",
            "hora_fin": "12:00",
            "zona_id": "1",
            "prioridad": "Media",
            "participant_ids": ["3"],
        },
        follow_redirects=True,
    )
    with app.app_context():
        meeting = Reunion.query.filter_by(titulo="Reunion Cancelable").first()
    response = client.post(f"/web/admin/reuniones/{meeting.id}/cancelar", data={"csrf_token": csrf}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Reunion.query.get(meeting.id).estado == "Cancelada"


def test_admin_puede_ver_logs(client):
    web_login(client)
    response = client.get("/web/admin/logs")
    assert response.status_code == 200
    assert "Logs de auditoria" in response.get_data(as_text=True)
    assert "Ver detalle tecnico" in response.get_data(as_text=True)


def test_vista_logs_no_muestra_password_hash_y_prioriza_descripcion(client):
    web_login(client)
    response = client.get("/web/admin/logs")
    body = response.get_data(as_text=True)
    assert "password_hash" not in body
    assert "inicio sesion" in body.lower() or "creo" in body.lower()


def test_admin_puede_ver_calendario_operativo(client):
    web_login(client)
    response = client.get("/web/admin/calendario?view=month")
    assert response.status_code == 200
    assert "Calendario operativo" in response.get_data(as_text=True)


def test_admin_puede_ver_calendario_por_zona(client):
    web_login(client)
    response = client.get("/web/admin/calendario?view=zone")
    assert response.status_code == 200
    assert "Vista agrupada" in response.get_data(as_text=True)


def test_dashboard_muestra_resumen_operativo(client):
    web_login(client)
    response = client.get("/web/admin")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Pendientes de respuesta" in body
    assert "Zonas ocupadas hoy" in body


def test_agendador_no_puede_acceder_admin(client):
    web_login(client, "agendador.contabilidad@empresa.local", "Agenda123!")
    response = client.get("/web/admin/usuarios")
    assert response.status_code == 403


def test_usuario_natural_no_puede_acceder_admin(client):
    web_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")
    response = client.get("/web/admin/usuarios")
    assert response.status_code == 403


def test_post_sin_csrf_se_rechaza(client):
    web_login(client)
    response = client.post(
        "/web/admin/areas/nueva",
        data={"nombre": "Sin CSRF", "descripcion": "x", "estado": "Activa"},
    )
    assert response.status_code == 403


def test_password_hash_no_aparece_en_html_ni_json(client):
    csrf = web_login(client)
    html = client.get("/web/admin/usuarios").get_data(as_text=True)
    assert "password_hash" not in html
    api = client.get("/api/usuarios", headers={"X-CSRF-Token": csrf}).get_data(as_text=True)
    assert "password_hash" not in api


def test_crear_reunion_con_participantes_seleccionados_funciona(client, app):
    csrf = web_login(client)
    response = client.post(
        "/web/admin/reuniones/nueva",
        data={
            "csrf_token": csrf,
            "titulo": "Reunion Chips",
            "motivo": "Uso del selector",
            "fecha": future_day(),
            "hora_inicio": "14:00",
            "hora_fin": "15:00",
            "zona_id": "1",
            "prioridad": "Alta",
            "participant_ids": ["3", "5"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Reunion.query.filter_by(titulo="Reunion Chips").first() is not None
