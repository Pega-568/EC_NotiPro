from __future__ import annotations

import json
import smtplib
import threading
import time as time_module
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib import error, request

from flask import current_app

from app.extensions import db
from app.models import (
    Configuracion,
    DeviceToken,
    EmailEvent,
    EmailLog,
    NotificationEvent,
    NotificationLog,
    Reunion,
    Usuario,
)


_dispatcher_lock = threading.Lock()
_dispatcher_started = False


def register_device_token(
    *,
    user_id: int,
    token: str,
    plataforma: str = "android",
    app_version: str | None = None,
    debug_ui: bool = False,
) -> DeviceToken:
    existing = DeviceToken.query.filter_by(token=token).first()
    if existing:
        existing.usuario_id = user_id
        existing.plataforma = plataforma
        existing.app_version = app_version
        existing.debug_ui = debug_ui
        existing.estado = "Activo"
        existing.ultimo_registro_at = datetime.utcnow()
        db.session.add(existing)
        return existing

    device = DeviceToken(
        usuario_id=user_id,
        token=token,
        plataforma=plataforma,
        app_version=app_version,
        debug_ui=debug_ui,
        estado="Activo",
        ultimo_registro_at=datetime.utcnow(),
    )
    db.session.add(device)
    db.session.flush()
    return device


def queue_meeting_notifications(meeting: Reunion, event_type: str, extra: dict | None = None) -> list[NotificationEvent]:
    recipients = _meeting_recipient_users(meeting)
    payload = _meeting_payload(meeting, recipients, extra)
    events: list[NotificationEvent] = []

    event = NotificationEvent(
        reunion_id=meeting.id,
        tipo_evento=event_type,
        estado="Pendiente",
        payload_json=json.dumps(payload, ensure_ascii=True),
    )
    db.session.add(event)
    db.session.flush()
    events.append(event)

    if event_type in {"meeting_created", "meeting_updated"}:
        meeting_start = datetime.combine(meeting.fecha, meeting.hora_inicio)
        for reminder_type, minutes in (("reminder_30", 30), ("reminder_10", 10)):
            reminder = NotificationEvent(
                reunion_id=meeting.id,
                tipo_evento=reminder_type,
                estado="Pendiente",
                payload_json=json.dumps(payload, ensure_ascii=True),
                programado_para=meeting_start - timedelta(minutes=minutes),
            )
            db.session.add(reminder)
            db.session.flush()
            events.append(reminder)
    return events


def queue_meeting_emails(meeting: Reunion, event_type: str, extra: dict | None = None) -> list[EmailEvent]:
    recipients = _meeting_recipient_users(meeting)
    programado_para = None
    if event_type == "reminder_30":
        programado_para = datetime.combine(meeting.fecha, meeting.hora_inicio) - timedelta(minutes=30)
    elif event_type == "reminder_10":
        programado_para = datetime.combine(meeting.fecha, meeting.hora_inicio) - timedelta(minutes=10)

    payload = _meeting_payload(meeting, recipients, extra)
    events: list[EmailEvent] = []
    for user in recipients:
        subject, body = _build_email_message(event_type, payload, user)
        event = EmailEvent(
            reunion_id=meeting.id,
            usuario_id=user.id,
            destinatario_correo=user.correo,
            tipo_evento=event_type,
            asunto=subject,
            cuerpo_texto=body,
            estado="Pendiente",
            programado_para=programado_para,
        )
        db.session.add(event)
        db.session.flush()
        events.append(event)
    return events


def register_dispatch_attempt(
    *,
    event_id: int | None,
    user_id: int | None,
    device_token_id: int | None,
    result: str,
    detail: str | None = None,
) -> NotificationLog:
    entry = NotificationLog(
        notification_event_id=event_id,
        usuario_id=user_id,
        device_token_id=device_token_id,
        resultado=result,
        detalle=detail,
        enviado_at=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def register_email_attempt(event: EmailEvent, result: str, detail: str | None = None) -> EmailLog:
    entry = EmailLog(
        email_event_id=event.id,
        resultado=result,
        detalle=detail,
        enviado_at=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def dispatch_pending_notifications(now: datetime | None = None, limit: int = 50) -> int:
    current_time = now or datetime.utcnow()
    pending_events = (
        NotificationEvent.query.filter_by(estado="Pendiente")
        .filter(
            (NotificationEvent.programado_para.is_(None))
            | (NotificationEvent.programado_para <= current_time)
        )
        .order_by(NotificationEvent.created_at.asc())
        .limit(limit)
        .all()
    )

    processed = 0
    for event in pending_events:
        _dispatch_event(event)
        processed += 1
    return processed


def dispatch_pending_emails(now: datetime | None = None, limit: int = 100) -> int:
    current_time = now or datetime.utcnow()
    pending_events = (
        EmailEvent.query.filter_by(estado="Pendiente")
        .filter((EmailEvent.programado_para.is_(None)) | (EmailEvent.programado_para <= current_time))
        .order_by(EmailEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for event in pending_events:
        _dispatch_email_event(event)
        processed += 1
    return processed


def dispatch_due_communications(now: datetime | None = None) -> dict[str, int]:
    return {
        "push": dispatch_pending_notifications(now=now),
        "email": dispatch_pending_emails(now=now),
    }


def start_background_dispatcher(app) -> None:
    global _dispatcher_started
    if _dispatcher_started or not app.config.get("BACKGROUND_DISPATCH_ENABLED"):
        return
    with _dispatcher_lock:
        if _dispatcher_started:
            return
        _dispatcher_started = True

        def _runner() -> None:
            while True:
                try:
                    with app.app_context():
                        dispatch_due_communications()
                        db.session.commit()
                except Exception:
                    with app.app_context():
                        db.session.rollback()
                time_module.sleep(app.config["BACKGROUND_DISPATCH_INTERVAL_SECONDS"])

        thread = threading.Thread(target=_runner, name="notification-dispatcher", daemon=True)
        thread.start()


def _dispatch_event(event: NotificationEvent) -> None:
    payload = json.loads(event.payload_json or "{}")
    if event.tipo_evento == "reminder_30" and not _config_enabled("recordatorio_30_minutos", True):
        event.estado = "Fallido"
        register_dispatch_attempt(
            event_id=event.id,
            user_id=None,
            device_token_id=None,
            result="fallido",
            detail="recordatorio_30_deshabilitado",
        )
        return
    if event.tipo_evento == "reminder_10" and not _config_enabled("recordatorio_10_minutos", True):
        event.estado = "Fallido"
        register_dispatch_attempt(
            event_id=event.id,
            user_id=None,
            device_token_id=None,
            result="fallido",
            detail="recordatorio_10_deshabilitado",
        )
        return

    recipient_ids = payload.get("recipient_ids") or []
    users = Usuario.query.filter(Usuario.id.in_(recipient_ids)).all() if recipient_ids else []
    sent_any = False

    for user in users:
        tokens = DeviceToken.query.filter_by(usuario_id=user.id, estado="Activo").all()
        if not tokens:
            register_dispatch_attempt(
                event_id=event.id,
                user_id=user.id,
                device_token_id=None,
                result="usuario_sin_dispositivo",
                detail="sin_token_activo",
            )
            continue
        for device in tokens:
            dispatch = _send_push(device.token, event.tipo_evento, payload)
            result = dispatch["result"]
            if result == "enviado":
                sent_any = True
            if result == "token_invalido":
                device.estado = "Invalido"
            register_dispatch_attempt(
                event_id=event.id,
                user_id=user.id,
                device_token_id=device.id,
                result=result,
                detail=dispatch.get("detail"),
            )

    event.estado = "Enviado" if sent_any else "Fallido"


def _dispatch_email_event(event: EmailEvent) -> None:
    if event.tipo_evento == "reminder_30" and not _config_enabled("recordatorio_30_minutos", True):
        event.estado = "Fallido"
        register_email_attempt(event, "fallido", "recordatorio_30_deshabilitado")
        return
    if event.tipo_evento == "reminder_10" and not _config_enabled("recordatorio_10_minutos", True):
        event.estado = "Fallido"
        register_email_attempt(event, "fallido", "recordatorio_10_deshabilitado")
        return
    if not current_app.config.get("MAIL_ENABLED"):
        event.estado = "Fallido"
        register_email_attempt(event, "fallido", "proveedor_mail_no_configurado")
        return

    try:
        _send_email(event.destinatario_correo, event.asunto, event.cuerpo_texto)
        event.estado = "Enviado"
        register_email_attempt(event, "enviado", "ok")
    except Exception as exc:
        event.estado = "Fallido"
        register_email_attempt(event, "fallido", str(exc)[:500])


def _send_email(to_address: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = to_address
    message["Reply-To"] = current_app.config["MAIL_REPLY_TO"]
    message["Subject"] = subject
    message.set_content(body)

    host = current_app.config["MAIL_HOST"]
    port = current_app.config["MAIL_PORT"]
    username = current_app.config["MAIL_USERNAME"]
    password = current_app.config["MAIL_PASSWORD"]

    if current_app.config["MAIL_USE_SSL"]:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    with server:
        if current_app.config["MAIL_USE_TLS"] and not current_app.config["MAIL_USE_SSL"]:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)


def _config_enabled(key: str, default: bool) -> bool:
    item = Configuracion.query.filter_by(clave=key).first()
    if not item:
        return default
    return item.valor.lower() == "true"


def _meeting_recipient_users(meeting: Reunion) -> list[Usuario]:
    by_id: dict[int, Usuario] = {meeting.responsable.id: meeting.responsable}
    by_id[meeting.creador.id] = meeting.creador
    for participant in meeting.participantes:
        by_id[participant.usuario.id] = participant.usuario
    return list(by_id.values())


def _meeting_payload(meeting: Reunion, recipients: list[Usuario], extra: dict | None = None) -> dict:
    payload = {
        "meeting_id": meeting.id,
        "title": meeting.titulo,
        "motivo": meeting.motivo,
        "date": meeting.fecha.isoformat(),
        "start": meeting.hora_inicio.strftime("%H:%M"),
        "end": meeting.hora_fin.strftime("%H:%M"),
        "zone": meeting.zona.nombre,
        "area": meeting.area_origen.nombre,
        "responsable_nombre": meeting.responsable.nombre,
        "responsable_correo": meeting.responsable.correo,
        "creator_nombre": meeting.creador.nombre,
        "recipient_ids": [user.id for user in recipients],
    }
    if extra:
        payload.update(extra)
    return payload


def _send_push(device_token: str, event_type: str, payload: dict) -> dict:
    if not current_app.config.get("FCM_ENABLED") or not current_app.config.get("FCM_SERVER_KEY"):
        return {"result": "fallido", "detail": "proveedor_push_no_configurado"}

    title, body, channel_id = _build_push_message(event_type, payload)
    data = {
        "to": device_token,
        "priority": "high",
        "notification": {
            "title": title,
            "body": body,
        },
        "data": {
            "meeting_id": str(payload.get("meeting_id", "")),
            "event_type": event_type,
            "screen": "meeting_detail",
            "title": payload.get("title", ""),
            "body": body,
            "channel_id": channel_id,
        },
    }
    req = request.Request(
        current_app.config["FCM_ENDPOINT"],
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"key={current_app.config['FCM_SERVER_KEY']}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw or "{}")
            if parsed.get("failure"):
                result_items = parsed.get("results") or [{}]
                error_code = result_items[0].get("error")
                if error_code in {"NotRegistered", "InvalidRegistration"}:
                    return {"result": "token_invalido", "detail": error_code}
                return {"result": "fallido", "detail": error_code or "fcm_failure"}
            return {"result": "enviado", "detail": "ok"}
    except error.HTTPError as exc:
        return {"result": "fallido", "detail": f"http_{exc.code}"}
    except error.URLError:
        return {"result": "fallido", "detail": "network_error"}


def _build_push_message(event_type: str, payload: dict) -> tuple[str, str, str]:
    title = payload.get("title", "Reunion institucional")
    date_text = payload.get("date", "")
    time_text = f"{payload.get('start', '')} - {payload.get('end', '')}".strip()
    zone = payload.get("zone", "")
    responder = payload.get("responder_nombre", "")
    response_status = payload.get("response_status", "")

    if event_type == "meeting_created":
        return title, f"Nueva reunion {date_text} {time_text} en {zone}.", "reuniones"
    if event_type == "meeting_updated":
        return title, f"Se actualizo la reunion {date_text} {time_text} en {zone}.", "reuniones"
    if event_type == "meeting_canceled":
        return title, f"La reunion programada para {date_text} fue cancelada.", "urgentes"
    if event_type == "meeting_response":
        return title, f"{responder} marco la reunion como {response_status}.", "reuniones"
    if event_type == "reminder_30":
        return title, "Recordatorio: la reunion inicia en 30 minutos.", "recordatorios"
    if event_type == "reminder_10":
        return title, "Recordatorio: la reunion inicia en 10 minutos.", "urgentes"
    return title, "Tiene una actualizacion de reunion.", "reuniones"


def _build_email_message(event_type: str, payload: dict, recipient: Usuario) -> tuple[str, str]:
    prefix = current_app.config["MAIL_SUBJECT_PREFIX"]
    subject = f"{prefix} {payload['title']}".strip()
    responsible = payload.get("responsable_nombre", "Sin responsable")
    response_status = payload.get("response_status", "")
    response_reason = payload.get("response_reason", "")
    responder = payload.get("responder_nombre", "")
    detail_url = f"{current_app.config['INTERNAL_BASE_URL'].rstrip('/')}/web/admin/reuniones/{payload['meeting_id']}"

    intro = f"Estimado/a {recipient.nombre},"
    common = (
        f"\n\nSe informa la novedad de la reunion institucional '{payload['title']}'."
        f"\nFecha: {payload['date']}"
        f"\nHorario: {payload['start']} - {payload['end']}"
        f"\nZona: {payload['zone']}"
        f"\nArea solicitante: {payload['area']}"
        f"\nResponsable de reunion: {responsible}"
        f"\nDetalle interno: {detail_url}"
    )

    if event_type == "meeting_created":
        body = intro + common + "\n\nAccion requerida: revise su agenda y registre su respuesta en la app institucional."
    elif event_type == "meeting_updated":
        body = intro + common + "\n\nSe han actualizado los datos de la reunion. Revise los cambios y confirme su disponibilidad."
    elif event_type == "meeting_canceled":
        body = intro + common + "\n\nLa reunion fue cancelada. No se requiere accion adicional."
    elif event_type == "meeting_response":
        body = (
            intro
            + common
            + f"\n\nRespuesta registrada por {responder}: {response_status}."
            + (f"\nMotivo informado: {response_reason}" if response_reason else "")
        )
    elif event_type == "reminder_30":
        body = intro + common + "\n\nRecordatorio automatico: la reunion iniciara en 30 minutos."
    elif event_type == "reminder_10":
        body = intro + common + "\n\nRecordatorio automatico: la reunion iniciara en 10 minutos."
    else:
        body = intro + common

    body += "\n\nAtentamente,\nSistema interno EC_NotiPro - Ecuamatriz"
    return subject, body
