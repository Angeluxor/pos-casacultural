"""anulación de ingresos de inventario

Agrega a ``ingresos_inventario`` los campos de anulación (bandera, motivo,
fecha y usuario) para corregir errores sin borrar el registro. El ingreso
anulado se conserva para auditoría, pero deja de contar en inventario, caja,
costos y cuentas por pagar.

También agrega el tipo de movimiento de kardex ``SALIDA_ANULACION`` para
registrar la reversión del stock de una compra anulada.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    op.add_column(
        "ingresos_inventario",
        sa.Column(
            "anulada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("motivo_anulacion", sa.String(), nullable=True),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("fecha_anulacion", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("anulada_por_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ingresos_inventario_anulada_por_id_usuarios",
        "ingresos_inventario",
        "usuarios",
        ["anulada_por_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_ingresos_inventario_anulada"),
        "ingresos_inventario",
        ["anulada"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingresos_inventario_anulada_por_id"),
        "ingresos_inventario",
        ["anulada_por_id"],
        unique=False,
    )

    if es_postgres:
        # PostgreSQL no permite quitar valores de un ENUM en el downgrade; el
        # valor agregado se deja para no romper registros históricos.
        op.execute(
            "ALTER TYPE tipomovimientoinventario "
            "ADD VALUE IF NOT EXISTS 'SALIDA_ANULACION'"
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ingresos_inventario_anulada_por_id"),
        table_name="ingresos_inventario",
    )
    op.drop_index(
        op.f("ix_ingresos_inventario_anulada"),
        table_name="ingresos_inventario",
    )
    op.drop_constraint(
        "fk_ingresos_inventario_anulada_por_id_usuarios",
        "ingresos_inventario",
        type_="foreignkey",
    )
    op.drop_column("ingresos_inventario", "anulada_por_id")
    op.drop_column("ingresos_inventario", "fecha_anulacion")
    op.drop_column("ingresos_inventario", "motivo_anulacion")
    op.drop_column("ingresos_inventario", "anulada")
