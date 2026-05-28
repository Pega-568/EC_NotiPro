from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Role(db.Model):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)


class Area(TimestampMixin, db.Model):
    __tablename__ = "areas"
    __table_args__ = (
        CheckConstraint("estado IN ('Activa', 'Inactiva')", name="ck_areas_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(db.String(255))
    estado: Mapped[str] = mapped_column(db.String(20), default="Activa", nullable=False)


class Usuario(TimestampMixin, db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("correo", name="uq_usuarios_correo"),
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="ck_usuarios_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(120), nullable=False)
    correo: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    telefono: Mapped[str | None] = mapped_column(db.String(30))
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    estado: Mapped[str] = mapped_column(db.String(20), default="Activo", nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None]
    ultimo_login_at: Mapped[datetime | None]

    role: Mapped[Role] = relationship()
    area: Mapped[Area] = relationship()


class ZonaReunion(TimestampMixin, db.Model):
    __tablename__ = "zonas_reunion"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('Activa', 'Inactiva', 'En mantenimiento')", name="ck_zonas_estado"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False)
    ubicacion: Mapped[str] = mapped_column(db.String(255), nullable=False)
    capacidad: Mapped[int] = mapped_column(nullable=False)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"))
    estado: Mapped[str] = mapped_column(db.String(30), default="Activa", nullable=False)
    margen_operativo_minutos: Mapped[int] = mapped_column(default=5, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(db.String(255))

    area: Mapped[Area | None] = relationship()


class Reunion(TimestampMixin, db.Model):
    __tablename__ = "reuniones"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('Pendiente', 'Aceptada', 'Rechazada', 'Cancelada', 'Finalizada')",
            name="ck_reuniones_estado",
        ),
        CheckConstraint(
            "prioridad IN ('Baja', 'Media', 'Alta')",
            name="ck_reuniones_prioridad",
        ),
        Index("ix_reuniones_fecha_hora", "fecha", "hora_inicio", "hora_fin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(db.String(150), nullable=False)
    motivo: Mapped[str] = mapped_column(db.String(500), nullable=False)
    creador_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    area_origen_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    zona_id: Mapped[int] = mapped_column(ForeignKey("zonas_reunion.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(nullable=False)
    hora_inicio: Mapped[time] = mapped_column(nullable=False)
    hora_fin: Mapped[time] = mapped_column(nullable=False)
    estado: Mapped[str] = mapped_column(db.String(20), default="Pendiente", nullable=False)
    prioridad: Mapped[str] = mapped_column(db.String(20), default="Media", nullable=False)

    creador: Mapped[Usuario] = relationship(foreign_keys=[creador_id])
    area_origen: Mapped[Area] = relationship()
    zona: Mapped[ZonaReunion] = relationship()
    participantes: Mapped[list[ReunionParticipante]] = relationship(
        back_populates="reunion", cascade="all, delete-orphan"
    )


class ReunionParticipante(db.Model):
    __tablename__ = "reunion_participantes"
    __table_args__ = (
        UniqueConstraint("reunion_id", "usuario_id", name="uq_reunion_participante"),
        CheckConstraint(
            "estado_respuesta IN ('Pendiente', 'Aceptada', 'Rechazada')",
            name="ck_participantes_estado_respuesta",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reunion_id: Mapped[int] = mapped_column(ForeignKey("reuniones.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    estado_respuesta: Mapped[str] = mapped_column(
        db.String(20), default="Pendiente", nullable=False
    )
    razon_rechazo: Mapped[str | None] = mapped_column(db.String(500))
    fecha_respuesta: Mapped[datetime | None]

    reunion: Mapped[Reunion] = relationship(back_populates="participantes")
    usuario: Mapped[Usuario] = relationship()


class Configuracion(db.Model):
    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(db.String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(db.String(255), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(db.String(255))


class DeviceToken(TimestampMixin, db.Model):
    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_token"),
        CheckConstraint("plataforma IN ('android')", name="ck_device_token_plataforma"),
        CheckConstraint("estado IN ('Activo', 'Inactivo', 'Invalido')", name="ck_device_token_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(db.String(255), nullable=False)
    plataforma: Mapped[str] = mapped_column(db.String(30), default="android", nullable=False)
    estado: Mapped[str] = mapped_column(db.String(20), default="Activo", nullable=False)
    app_version: Mapped[str | None] = mapped_column(db.String(50))
    debug_ui: Mapped[bool] = mapped_column(default=False, nullable=False)
    ultimo_registro_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    usuario: Mapped[Usuario] = relationship()


class NotificationEvent(TimestampMixin, db.Model):
    __tablename__ = "notification_events"
    __table_args__ = (
        CheckConstraint(
            "tipo_evento IN ('meeting_created', 'meeting_updated', 'meeting_canceled', 'reminder_30', 'reminder_10')",
            name="ck_notification_event_tipo",
        ),
        CheckConstraint("estado IN ('Pendiente', 'Enviado', 'Fallido')", name="ck_notification_event_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reunion_id: Mapped[int | None] = mapped_column(ForeignKey("reuniones.id"))
    tipo_evento: Mapped[str] = mapped_column(db.String(40), nullable=False)
    estado: Mapped[str] = mapped_column(db.String(20), default="Pendiente", nullable=False)
    payload_json: Mapped[str | None] = mapped_column(db.Text)
    programado_para: Mapped[datetime | None]

    reunion: Mapped[Reunion | None] = relationship()


class NotificationLog(TimestampMixin, db.Model):
    __tablename__ = "notification_logs"
    __table_args__ = (
        CheckConstraint(
            "resultado IN ('enviado', 'fallido', 'usuario_sin_dispositivo', 'token_invalido')",
            name="ck_notification_log_resultado",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_event_id: Mapped[int | None] = mapped_column(ForeignKey("notification_events.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    device_token_id: Mapped[int | None] = mapped_column(ForeignKey("device_tokens.id"))
    resultado: Mapped[str] = mapped_column(db.String(30), nullable=False)
    detalle: Mapped[str | None] = mapped_column(db.String(500))
    enviado_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    event: Mapped[NotificationEvent | None] = relationship()
    usuario: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_id])
    device_token: Mapped[DeviceToken | None] = relationship(foreign_keys=[device_token_id])


class LogSistema(db.Model):
    __tablename__ = "logs_sistema"
    __table_args__ = (
        Index("ix_logs_fecha_hora", "fecha_hora"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_actor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    rol_actor: Mapped[str | None] = mapped_column(db.String(50))
    accion: Mapped[str] = mapped_column(db.String(100), nullable=False)
    entidad: Mapped[str] = mapped_column(db.String(100), nullable=False)
    entidad_id: Mapped[str | None] = mapped_column(db.String(50))
    resultado: Mapped[str] = mapped_column(db.String(30), nullable=False)
    descripcion_humana: Mapped[str | None] = mapped_column(db.String(1000))
    detalle_seguro: Mapped[str | None] = mapped_column(db.String(1000))
    ip: Mapped[str | None] = mapped_column(db.String(64))
    user_agent: Mapped[str | None] = mapped_column(db.String(255))
    fecha_hora: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    usuario_actor: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_actor_id])


class UserSession(db.Model):
    __tablename__ = "sesiones"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sesiones_token_hash"),
        Index("ix_sesiones_usuario_id", "usuario_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    csrf_token: Mapped[str] = mapped_column(db.String(64), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(nullable=False)
    activa: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    usuario: Mapped[Usuario] = relationship()
