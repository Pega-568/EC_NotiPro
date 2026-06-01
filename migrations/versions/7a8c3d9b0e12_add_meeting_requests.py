"""add meeting requests

Revision ID: 7a8c3d9b0e12
Revises: 9c9dd1d9c4f7
Create Date: 2026-06-01 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "7a8c3d9b0e12"
down_revision = "9c9dd1d9c4f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reunion_solicitudes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitante_usuario_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("motivo", sa.String(length=500), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("zona_id", sa.Integer(), nullable=False),
        sa.Column("prioridad", sa.String(length=20), nullable=False, server_default="Media"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.Column("observacion_solicitante", sa.String(length=500), nullable=True),
        sa.Column("respuesta_secretaria", sa.String(length=500), nullable=True),
        sa.Column("revisada_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("revisada_at", sa.DateTime(), nullable=True),
        sa.Column("reunion_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('Pendiente', 'Aprobada', 'Rechazada', 'Cancelada')",
            name="ck_solicitudes_estado",
        ),
        sa.CheckConstraint(
            "prioridad IN ('Baja', 'Media', 'Alta')",
            name="ck_solicitudes_prioridad",
        ),
        sa.ForeignKeyConstraint(["solicitante_usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["zona_id"], ["zonas_reunion.id"]),
        sa.ForeignKeyConstraint(["revisada_por_usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["reunion_id"], ["reuniones.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reunion_solicitud_participantes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("area_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["solicitud_id"], ["reunion_solicitudes.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("solicitud_id", "usuario_id", name="uq_solicitud_participante"),
    )


def downgrade():
    op.drop_table("reunion_solicitud_participantes")
    op.drop_table("reunion_solicitudes")
