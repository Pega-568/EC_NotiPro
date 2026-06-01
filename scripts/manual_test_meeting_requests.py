from datetime import date, time, timedelta, datetime
import sys
from app import create_app
from app.extensions import db
from app.models import Usuario, ZonaReunion, ReunionSolicitud, Reunion, ReunionParticipante
from app.services.seeds import seed_defaults
from app.services.meeting_requests import (
    check_availability,
    create_meeting_request,
    approve_meeting_request,
)

def run_verification():
    print("======================================================================")
    print("INICIANDO PRUEBA DE VERIFICACIÓN MANUAL END-TO-END CON POSTGRESQL")
    print("======================================================================")

    # 1. Initialize Flask App Context
    app = create_app()
    with app.test_request_context():
        # Clear database and seed fresh catalogs and demo users
        print("\n--- PASO 1: Re-inicializar y sembrar base de datos PostgreSQL ---")
        db.drop_all()
        db.create_all()
        seed_defaults()
        print("Base de datos limpia y poblada con datos semilla de demostración.")

        # Query actors and entities
        colaborador = Usuario.query.filter_by(correo="usuario1.contabilidad@empresa.local").first()
        participante = Usuario.query.filter_by(correo="usuario2.contabilidad@empresa.local").first()
        secretaria = Usuario.query.filter_by(correo="secretaria.general@empresa.local").first()
        zona = ZonaReunion.query.filter_by(nombre="Sala Principal").first()

        assert colaborador is not None, "No se encontró el colaborador."
        assert participante is not None, "No se encontró el participante."
        assert secretaria is not None, "No se encontró la secretaria."
        assert zona is not None, "No se encontró la sala principal."

        print(f"Colaborador: {colaborador.nombre} (ID: {colaborador.id}, Rol: {colaborador.role.nombre})")
        print(f"Participante: {participante.nombre} (ID: {participante.id}, Rol: {participante.role.nombre})")
        print(f"Secretaría: {secretaria.nombre} (ID: {secretaria.id}, Rol: {secretaria.role.nombre})")
        print(f"Sala de reunión: {zona.nombre} (ID: {zona.id}, Ubicación: {zona.ubicacion})")

        # 2. Check initial availability (should be available)
        print("\n--- PASO 2: Verificar disponibilidad inicial ---")
        fecha_req = date.today() + timedelta(days=2)
        hora_ini = time(10, 0)
        hora_fin = time(11, 0)

        avail = check_availability(fecha_req, hora_ini, hora_fin)
        room_avail = next(z for z in avail["zonas"] if z["id"] == zona.id)
        user_avail = next(u for u in avail["usuarios"] if u["id"] == participante.id)

        print(f"Disponibilidad de {zona.nombre}: {'Disponible' if room_avail['disponible'] else 'Ocupada'}")
        print(f"Disponibilidad de {participante.nombre}: {'Disponible' if user_avail['disponible'] else 'Ocupado'}")

        assert room_avail["disponible"] is True, "La sala principal debería estar disponible."
        assert user_avail["disponible"] is True, "El participante debería estar disponible."

        # 3. Colaborador creates a Meeting Request
        print("\n--- PASO 3: Crear solicitud de reunión como Colaborador ---")
        payload = {
            "titulo": "Sincronización Semanal de Contabilidad",
            "motivo": "Revisión de reportes y facturas pendientes",
            "fecha": fecha_req.isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "11:00",
            "zona_id": zona.id,
            "participant_ids": [participante.id],
            "observacion_solicitante": "Traer reportes del mes anterior",
        }
        
        # Set request actor context
        from flask import g
        g.current_user = colaborador
        
        solicitud = create_meeting_request(payload, colaborador)
        print(f"Solicitud creada con éxito! ID: {solicitud.id}")
        print(f"Título: {solicitud.titulo}")
        print(f"Estado: {solicitud.estado}")
        
        assert solicitud.id is not None
        assert solicitud.estado == "Pendiente"

        # 4. Confirm availability with pending request (should show as unavailable due to pending request)
        print("\n--- PASO 4: Confirmar que el participante y la sala aparecen ocupados por solicitud pendiente ---")
        avail_pending = check_availability(fecha_req, hora_ini, hora_fin)
        user_pending_avail = next(u for u in avail_pending["usuarios"] if u["id"] == participante.id)
        
        print(f"Participante {participante.nombre} disponible? {user_pending_avail['disponible']}")
        print(f"Motivo: {user_pending_avail['motivo']}")
        
        assert user_pending_avail["disponible"] is False
        assert "Solicitud pendiente" in user_pending_avail["motivo"]

        # 5. Secretary approves the Meeting Request, selecting a custom meeting responsible
        print("\n--- PASO 5: Secretaría revisa y aprueba la solicitud ---")
        # Change active actor context to Secretary
        g.current_user = secretaria

        # The secretary selects the participant (Usuario 2) as the responsible for the meeting
        reunion = approve_meeting_request(solicitud.id, secretaria, responsable_reunion_id=participante.id)
        
        print(f"Solicitud aprobada con éxito!")
        print(f"Reunión Creada - ID: {reunion.id}")
        print(f"Título: {reunion.titulo}")
        print(f"Responsable asignado (ID): {reunion.responsable_reunion_id} ({reunion.responsable.nombre})")
        print(f"Estado de la Solicitud ahora: {solicitud.estado}")
        
        assert reunion.id is not None
        assert reunion.responsable_reunion_id == participante.id, "El responsable debería ser el participante seleccionado."
        assert solicitud.estado == "Aprobada"
        assert solicitud.reunion_id == reunion.id

        # 6. Confirm that the approved meeting blocks further requests (user and room are busy)
        print("\n--- PASO 6: Confirmar que el participante y la sala aparecen ocupados por la reunión aprobada ---")
        avail_approved = check_availability(fecha_req, hora_ini, hora_fin)
        room_approved_avail = next(z for z in avail_approved["zonas"] if z["id"] == zona.id)
        user_approved_avail = next(u for u in avail_approved["usuarios"] if u["id"] == participante.id)
        
        print(f"Sala {zona.nombre} disponible? {room_approved_avail['disponible']} (Motivo: {room_approved_avail['motivo']})")
        print(f"Participante {participante.nombre} disponible? {user_approved_avail['disponible']} (Motivo: {user_approved_avail['motivo']})")
        
        assert room_approved_avail["disponible"] is False
        assert room_approved_avail["motivo"] == "Sala ocupada en ese horario"
        assert user_approved_avail["disponible"] is False
        assert user_approved_avail["motivo"] == "Este usuario ya posee una reunión"

        print("\n======================================================================")
        print("¡TODAS LAS PRUEBAS DE FLUJO MANUAL PASARON EXITOSAMENTE EN POSTGRESQL!")
        print("======================================================================")

if __name__ == "__main__":
    try:
        run_verification()
    except Exception as e:
        print(f"\n[ERROR] Falló la verificación manual: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
