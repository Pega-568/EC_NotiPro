"""backend hardening future backend tables

Revision ID: 9c9dd1d9c4f7
Revises: e186e44cc682
Create Date: 2026-05-28 10:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "9c9dd1d9c4f7"
down_revision = "e186e44cc682"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("reunion_historial", schema=None) as batch_op:
        batch_op.drop_constraint("ck_reunion_historial_tipo", type_="check")
        batch_op.create_check_constraint(
            "ck_reunion_historial_tipo",
            (
                "tipo_evento IN ("
                "'created', 'updated', 'canceled', 'response', 'finalized', "
                "'participant_added', 'participant_removed'"
                ")"
            ),
        )

    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=100), nullable=False),
        sa.Column("asunto_template", sa.String(length=255), nullable=False),
        sa.Column("cuerpo_template", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_email_templates_codigo"),
    )

    op.create_table(
        "asistencias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reunion_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("estado_asistencia", sa.String(length=20), nullable=False),
        sa.Column("marcada_at", sa.DateTime(), nullable=True),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "estado_asistencia IN ('Pendiente', 'Presente', 'Ausente', 'Justificada')",
            name="ck_asistencias_estado",
        ),
        sa.ForeignKeyConstraint(["reunion_id"], ["reuniones.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reunion_id", "usuario_id", name="uq_asistencias_reunion_usuario"),
    )

    op.create_table(
        "qr_asistencia_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reunion_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expira_en", sa.DateTime(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("estado IN ('Activo', 'Consumido', 'Expirado')", name="ck_qr_asistencia_estado"),
        sa.ForeignKeyConstraint(["reunion_id"], ["reuniones.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_qr_asistencia_token_hash"),
    )

    op.create_table(
        "actas_reunion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reunion_id", sa.Integer(), nullable=False),
        sa.Column("redactada_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("resumen", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("estado IN ('Borrador', 'Cerrada')", name="ck_actas_reunion_estado"),
        sa.ForeignKeyConstraint(["reunion_id"], ["reuniones.id"]),
        sa.ForeignKeyConstraint(["redactada_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reunion_id", name="uq_actas_reunion_reunion"),
    )

    op.create_table(
        "acta_orden_dia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("acta_reunion_id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["acta_reunion_id"], ["actas_reunion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "acta_acuerdos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("acta_reunion_id", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("responsable_usuario_id", sa.Integer(), nullable=True),
        sa.Column("fecha_compromiso", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('Pendiente', 'En progreso', 'Cumplido', 'Descartado')",
            name="ck_acta_acuerdos_estado",
        ),
        sa.ForeignKeyConstraint(["acta_reunion_id"], ["actas_reunion.id"]),
        sa.ForeignKeyConstraint(["responsable_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "acta_asistentes_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("acta_reunion_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("correo", sa.String(length=255), nullable=True),
        sa.Column("estado_respuesta", sa.String(length=20), nullable=True),
        sa.Column("estado_asistencia", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["acta_reunion_id"], ["actas_reunion.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("acta_asistentes_snapshot")
    op.drop_table("acta_acuerdos")
    op.drop_table("acta_orden_dia")
    op.drop_table("actas_reunion")
    op.drop_table("qr_asistencia_tokens")
    op.drop_table("asistencias")
    op.drop_table("email_templates")

    with op.batch_alter_table("reunion_historial", schema=None) as batch_op:
        batch_op.drop_constraint("ck_reunion_historial_tipo", type_="check")
        batch_op.create_check_constraint(
            "ck_reunion_historial_tipo",
            "tipo_evento IN ('created', 'updated', 'canceled', 'response', 'finalized')",
        )
