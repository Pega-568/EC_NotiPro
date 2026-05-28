from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib import error, request

from flask import current_app

from app.extensions import db
from app.models import Configuracion, DeviceToken, NotificationEvent, NotificationLog, Reunion, Usuario


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


def queue_meeting_notifications(meeting: Reunion, event_type: str) -> list[NotificationEvent]:
    participants = [row.usuario for row in meeting.participantes]
    payload = {
        "meeting_id": meeting.id,
        "title": meeting.titulo,
        "date": meeting.fecha.isoformat(),
        "start": meeting.hora_inicio.strftime("%H:%M"),
        "end": meeting.hora_fin.strftime("%H:%M"),
        "zone": meeting.zona.nombre,
        "participant_ids": [user.id for user in participants],
    }
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

    participant_ids = payload.get("participant_ids") or []
    users = Usuario.query.filter(Usuario.id.in_(participant_ids)).all() if participant_ids else []
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


def _config_enabled(key: str, default: bool) -> bool:
    item = Configuracion.query.filter_by(clave=key).first()
    if not item:
        return default
    return item.valor.lower() == "true"


def _send_push(device_token: str, event_type: str, payload: dict) -> dict:
    if not current_app.config.get("FCM_ENABLED") or not current_app.config.get("FCM_SERVER_KEY"):
        return {"result": "fallido", "detail": "proveedor_push_no_configurado"}

    title, body, channel_id = _build_message(event_type, payload)
    data = {
        "to": device_token,
        "priority": "high",
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


def _build_message(event_type: str, payload: dict) -> tuple[str, str, str]:
    title = payload.get("title", "Reunión institucional")
    date_text = payload.get("date", "")
    time_text = f"{payload.get('start', '')} - {payload.get('end', '')}".strip()
    zone = payload.get("zone", "")

    if event_type == "meeting_created":
        return title, f"Nueva reunión {date_text} {time_text} en {zone}.", "reuniones"
    if event_type == "meeting_updated":
        return title, f"Se actualizó la reunión {date_text} {time_text}.", "reuniones"
    if event_type == "meeting_canceled":
        return title, f"La reunión programada para {date_text} fue cancelada.", "urgentes"
    if event_type == "reminder_30":
        return title, f"Recordatorio: la reunión inicia en 30 minutos.", "recordatorios"
    if event_type == "reminder_10":
        return title, f"Recordatorio: la reunión inicia en 10 minutos.", "urgentes"
    return title, "Tiene una actualización de reunión.", "reuniones"
