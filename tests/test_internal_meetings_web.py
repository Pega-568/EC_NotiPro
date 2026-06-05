from datetime import date, timedelta

from app.constants import ROLE_AGENDADOR
from app.extensions import db
from app.models import Reunion, Role, Usuario
from app.security import hash_password


def future_day(offset=1):
    return (date.today() + timedelta(days=offset)).isoformat()


def web_login(client, correo, password):
    response = client.post("/login", data={"correo": correo, "password": password})
    assert response.status_code == 302
    return client.get_cookie("csrf_token").value


def ensure_agendador(app):
    with app.app_context():
        role = Role.query.filter_by(nombre=ROLE_AGENDADOR).first()
        if not role:
            role = Role(nombre=ROLE_AGENDADOR)
            db.session.add(role)
            db.session.flush()
        user = Usuario.query.filter_by(correo="encargado.web@empresa.local").first()
        if not user:
            user = Usuario(
                nombre="Encargado Web",
                correo="encargado.web@empresa.local",
                telefono="0997770001",
                password_hash=hash_password("Encargado123!"),
                role_id=role.id,
                area_id=1,
            )
            db.session.add(user)
            db.session.commit()


def internal_payload(csrf, *, day=1, zone_id="2", start="09:00", end="10:00", participants=None):
    participants = participants or ["3", "4"]
    return {
        "csrf_token": csrf,
        "titulo": "Interna Web",
        "motivo": "Coordinacion directa de area",
        "fecha": future_day(day),
        "hora_inicio": start,
        "hora_fin": end,
        "zona_id": zone_id,
        "participant_ids": participants,
    }


def test_encargado_ve_boton_crear_reunion_interna(client, app):
    ensure_agendador(app)
    web_login(client, "encargado.web@empresa.local", "Encargado123!")

    response = client.get("/web/solicitudes")

    assert response.status_code == 200
    assert "Crear reunión interna" in response.get_data(as_text=True)


def test_colaborador_no_ve_boton_crear_reunion_interna(client):
    web_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")

    response = client.get("/web/solicitudes")

    assert response.status_code == 200
    assert "Crear reunión interna" not in response.get_data(as_text=True)


def test_encargado_abre_formulario_reunion_interna(client, app):
    ensure_agendador(app)
    web_login(client, "encargado.web@empresa.local", "Encargado123!")

    response = client.get("/web/admin/reuniones-internas/nueva")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Prioridad: Baja automatica" in body
    assert "No requiere aprobacion de Secretaria" in body
    assert "usuario2.contabilidad@empresa.local" in body
    assert "usuario1.mercado@empresa.local" not in body


def test_encargado_crea_reunion_interna_valida(client, app):
    ensure_agendador(app)
    csrf = web_login(client, "encargado.web@empresa.local", "Encargado123!")

    response = client.post(
        "/api/reuniones-internas",
        data=internal_payload(csrf),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Reunión interna creada correctamente." in response.get_data(as_text=True)
    with app.app_context():
        meeting = Reunion.query.filter_by(titulo="Interna Web").first()
        assert meeting is not None
        assert meeting.prioridad == "Baja"


def test_encargado_no_puede_crear_con_usuario_de_otra_area(client, app):
    ensure_agendador(app)
    csrf = web_login(client, "encargado.web@empresa.local", "Encargado123!")

    response = client.post(
        "/api/reuniones-internas",
        data=internal_payload(csrf, participants=["3", "5"]),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "solo puede crear reuniones internas con participantes de su area" in response.get_data(as_text=True)
    with app.app_context():
        assert Reunion.query.filter_by(titulo="Interna Web").first() is None


def test_colaborador_no_puede_acceder_formulario_por_url_directa(client):
    web_login(client, "usuario1.contabilidad@empresa.local", "Usuario123!")

    response = client.get("/web/admin/reuniones-internas/nueva")

    assert response.status_code == 403


def test_secretaria_y_admin_pueden_acceder_formulario_reunion_interna(client):
    web_login(client, "secretaria.general@empresa.local", "Agenda123!")
    secretaria_response = client.get("/web/admin/reuniones-internas/nueva")
    assert secretaria_response.status_code == 200

    client.post("/logout", data={"csrf_token": client.get_cookie("csrf_token").value})
    web_login(client, "admin@empresa.local", "Admin123!")
    admin_response = client.get("/web/admin/reuniones-internas/nueva")
    assert admin_response.status_code == 200


def test_exito_redirige_a_detalle_de_reunion(client, app):
    ensure_agendador(app)
    csrf = web_login(client, "encargado.web@empresa.local", "Encargado123!")

    response = client.post("/api/reuniones-internas", data=internal_payload(csrf), follow_redirects=False)

    assert response.status_code == 302
    assert "/web/admin/reuniones/" in response.headers["Location"]
    assert "success=" in response.headers["Location"]


def test_error_backend_se_muestra_amigable(client):
    csrf = web_login(client, "secretaria.general@empresa.local", "Agenda123!")
    first = client.post(
        "/api/reuniones-internas",
        data=internal_payload(csrf, day=2, zone_id="1", participants=["3"]),
    )
    assert first.status_code == 302

    response = client.post(
        "/api/reuniones-internas",
        data=internal_payload(csrf, day=2, zone_id="1", start="09:30", end="10:30", participants=["4"]),
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "La zona ya esta reservada" in body
