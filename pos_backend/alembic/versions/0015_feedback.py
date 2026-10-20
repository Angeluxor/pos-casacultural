"""feedback del equipo con captura y bandeja de gestión

Crea ``feedback``: comentarios, ideas y reportes de error enviados por los
usuarios desde el botón flotante. Incluye contexto técnico, captura opcional
(almacenada en la base de datos) y los campos de gestión de la bandeja:
estado, prioridad, etiquetas, responsable y notas internas.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("contexto", sa.JSON(), nullable=False),
        sa.Column(
            "estado", sa.String(), nullable=False, server_default="Nuevo"
        ),
        sa.Column(
            "prioridad", sa.String(), nullable=False, server_default="Media"
        ),
        sa.Column("etiquetas", sa.String(), nullable=True),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("notas_internas", sa.Text(), nullable=True),
        sa.Column(
            "tiene_captura",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("captura", sa.LargeBinary(), nullable=True),
        sa.Column("captura_mime", sa.String(), nullable=True),
        sa.Column("captura_nombre", sa.String(), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["responsable_id"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_id"), "feedback", ["id"], unique=False)
    op.create_index(
        op.f("ix_feedback_usuario_id"), "feedback", ["usuario_id"], unique=False
    )
    op.create_index(op.f("ix_feedback_tipo"), "feedback", ["tipo"], unique=False)
    op.create_index(op.f("ix_feedback_estado"), "feedback", ["estado"], unique=False)
    op.create_index(
        op.f("ix_feedback_prioridad"), "feedback", ["prioridad"], unique=False
    )
    op.create_index(
        op.f("ix_feedback_responsable_id"),
        "feedback",
        ["responsable_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_creado_en"), "feedback", ["creado_en"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_creado_en"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_responsable_id"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_prioridad"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_estado"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_tipo"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_usuario_id"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_id"), table_name="feedback")
    op.drop_table("feedback")
