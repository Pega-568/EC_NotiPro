from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from app import create_app
from app.models import Reunion, ReunionSolicitud


BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:5000")
SCREENSHOT_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "web-ui-polish"


USERS = {
    "admin": ("admin@empresa.local", "Admin123!"),
    "secretaria": ("secretaria.general@empresa.local", "Agenda123!"),
    "colaborador": ("usuario1.contabilidad@empresa.local", "Usuario123!"),
    "agendador": ("agendador.contabilidad@empresa.local", "Agenda123!"),
}


def login(page, email: str, password: str) -> None:
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.fill('input[name="correo"]', email)
    page.fill('input[name="password"]', password)
    page.click("button:has-text('Entrar')")
    page.wait_for_load_state("networkidle")


def logout(page) -> None:
    page.click("[data-user-menu-button]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Cerrar sesión')")
    page.wait_for_load_state("networkidle")


def nav_text(page) -> str:
    return page.locator("nav").inner_text()


def expand_sidebar(page) -> None:
    page.evaluate(
        """() => {
            localStorage.removeItem('ecnp-sidebar-collapsed');
            document.querySelector('[data-app-shell]')?.classList.remove('sidebar-collapsed');
        }"""
    )


def fill_request(page, *, title: str, start: str, end: str, participant_name: str = "Colaborador 2 Contabilidad") -> None:
    page.goto(f"{BASE_URL}/web/solicitudes/nueva", wait_until="networkidle")
    page.fill("#titulo", title)
    page.fill("#motivo", f"Validacion E2E para {title}")
    page.fill("#fecha", "2026-06-02")
    page.fill("#hora_inicio", start)
    page.fill("#hora_fin", end)
    page.wait_for_timeout(700)
    zone_value = page.locator("#zona_id option", has_text="Sala Principal").first.get_attribute("value")
    assert zone_value is not None
    page.select_option("#zona_id", value=zone_value)
    page.get_by_label(participant_name).check()
    page.fill("#observacion_solicitante", "Solicitud generada por prueba funcional.")


def submit_request(page) -> int:
    page.click("button:has-text('Enviar Solicitud')")
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Solicitud de reunión creada exitosamente")
    page.click("a:has-text('Ver detalle')")
    page.wait_for_load_state("networkidle")
    return int(page.url.rstrip("/").split("/")[-1])


def validate_request_filters(page) -> None:
    page.fill("#participantSearch", "usuario2")
    expect(page.locator("[data-participant-card]", has_text="Colaborador 2 Contabilidad")).to_be_visible()
    expect(page.locator("[data-participant-card]", has_text="Administrador Principal")).to_be_hidden()
    page.fill("#participantSearch", "")
    page.select_option("#participantArea", label="Contabilidad")
    expect(page.locator("[data-participant-card]", has_text="Colaborador 1 Mercado")).to_be_hidden()
    page.select_option("#participantArea", value="")
    page.fill("#zoneCapacity", "15")
    expect(page.locator("[data-zone-card]", has_text="Sala Contabilidad")).to_be_hidden()
    expect(page.locator("[data-zone-card]", has_text="Sala Principal")).to_be_visible()
    page.fill("#zoneCapacity", "")


def approve_request(page, sol_id: int) -> int:
    page.goto(f"{BASE_URL}/web/secretaria/solicitudes/{sol_id}", wait_until="networkidle")
    page.screenshot(path=SCREENSHOT_DIR / "e2e_04_aprobacion.png", full_page=False)
    page.select_option("#responsable_reunion_id", index=0)
    page.click("button:has-text('Aprobar Solicitud')")
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Solicitud aprobada y reunión agendada exitosamente")

    app = create_app()
    with app.app_context():
        sol = ReunionSolicitud.query.get(sol_id)
        assert sol is not None
        assert sol.estado == "Aprobada"
        assert sol.reunion_id is not None
        meeting = Reunion.query.get(sol.reunion_id)
        assert meeting is not None
        return meeting.id


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    app = create_app()
    with app.app_context():
        initial_meetings = Reunion.query.count()

    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=edge_path, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        login(page, *USERS["admin"])
        expand_sidebar(page)
        expect(page).to_have_url(f"{BASE_URL}/web/admin")
        admin_nav = page.locator(".sidebar-nav").inner_text()
        for item in ("Panel", "Calendario", "Reuniones", "Solicitudes", "Usuarios", "Areas", "Zonas", "Logs", "Configuracion"):
            assert item in admin_nav, f"Admin no ve {item}"
        page.click("[data-sidebar-toggle]")
        page.screenshot(path=SCREENSHOT_DIR / "e2e_06_menu_colapsado.png", full_page=False)
        page.click("[data-sidebar-toggle]")
        logout(page)

        login(page, *USERS["secretaria"])
        expand_sidebar(page)
        sec_nav = page.locator(".sidebar-nav").inner_text()
        assert "Solicitudes" in sec_nav
        logout(page)

        login(page, *USERS["colaborador"])
        expand_sidebar(page)
        col_nav = page.locator(".sidebar-nav").inner_text()
        assert "Solicitar" in col_nav and "Mis solicitudes" in col_nav
        assert "Solicitudes" not in col_nav.replace("Mis solicitudes", "")
        fill_request(page, title="E2E Aprobacion Colaborador", start="10:00", end="11:00")
        validate_request_filters(page)
        page.screenshot(path=SCREENSHOT_DIR / "e2e_01_pantalla_solicitar.png", full_page=False)
        sol_id = submit_request(page)

        with app.app_context():
            sol = ReunionSolicitud.query.get(sol_id)
            assert sol is not None
            assert sol.estado == "Pendiente"
            assert sol.reunion_id is None
            assert Reunion.query.count() == initial_meetings
        logout(page)

        login(page, *USERS["agendador"])
        expand_sidebar(page)
        ag_nav = page.locator(".sidebar-nav").inner_text()
        assert "Solicitar" in ag_nav and "Mis solicitudes" in ag_nav
        assert "Solicitudes" not in ag_nav.replace("Mis solicitudes", "")
        logout(page)

        login(page, *USERS["secretaria"])
        page.goto(f"{BASE_URL}/web/secretaria/solicitudes", wait_until="networkidle")
        expect(page.locator("body")).to_contain_text("E2E Aprobacion Colaborador")
        page.screenshot(path=SCREENSHOT_DIR / "e2e_03_solicitudes_secretaria.png", full_page=False)
        meeting_id = approve_request(page, sol_id)
        page.goto(f"{BASE_URL}/web/admin/reuniones/{meeting_id}", wait_until="networkidle")
        expect(page.locator("body")).to_contain_text("E2E Aprobacion Colaborador")
        page.screenshot(path=SCREENSHOT_DIR / "e2e_05_reunion_creada.png", full_page=False)
        logout(page)

        login(page, *USERS["colaborador"])
        page.goto(f"{BASE_URL}/web/solicitudes/nueva", wait_until="networkidle")
        page.fill("#titulo", "E2E Conflicto Visual")
        page.fill("#motivo", "Intento sobre sala y usuario ocupado")
        page.fill("#fecha", "2026-06-02")
        page.fill("#hora_inicio", "10:00")
        page.fill("#hora_fin", "11:00")
        page.wait_for_timeout(900)
        expect(page.locator("#zona_id")).to_contain_text("[Sala ocupada en ese horario] Sala Principal")
        expect(page.locator("#participantsContainer")).to_contain_text("Este usuario ya posee una reunión")
        page.screenshot(path=SCREENSHOT_DIR / "e2e_02_usuarios_no_disponibles.png", full_page=False)

        fill_request(page, title="E2E Rechazo con Motivo", start="11:30", end="12:00")
        reject_id = submit_request(page)
        fill_request(page, title="E2E Cancelacion Propia", start="12:30", end="13:00")
        cancel_id = submit_request(page)
        page.goto(f"{BASE_URL}/web/solicitudes/{cancel_id}", wait_until="networkidle")
        page.once("dialog", lambda dialog: dialog.accept())
        page.click("button:has-text('Cancelar Solicitud')")
        page.wait_for_load_state("networkidle")
        expect(page.locator("body")).to_contain_text("Solicitud cancelada exitosamente")
        with app.app_context():
            canceled = ReunionSolicitud.query.get(cancel_id)
            assert canceled is not None
            assert canceled.estado == "Cancelada"
        logout(page)

        login(page, *USERS["secretaria"])
        page.goto(f"{BASE_URL}/web/secretaria/solicitudes/{reject_id}", wait_until="networkidle")
        page.click("button:has-text('Rechazar Solicitud')")
        page.fill("#reason", "No procede por ajuste de agenda validado en prueba E2E.")
        page.once("dialog", lambda dialog: dialog.accept())
        page.click("button:has-text('Confirmar Rechazo')")
        page.wait_for_load_state("networkidle")
        expect(page.locator("body")).to_contain_text("Solicitud rechazada exitosamente")
        with app.app_context():
            rejected = ReunionSolicitud.query.get(reject_id)
            assert rejected is not None
            assert rejected.estado == "Rechazada"
            assert "ajuste de agenda" in (rejected.respuesta_secretaria or "")

        browser.close()

    print("OK")
    print(f"Capturas: {SCREENSHOT_DIR.resolve()}")
    print(f"Solicitud aprobada: {sol_id}")
    print(f"Reunion creada: {meeting_id}")
    print(f"Solicitud rechazada: {reject_id}")
    print(f"Solicitud cancelada: {cancel_id}")


if __name__ == "__main__":
    main()
