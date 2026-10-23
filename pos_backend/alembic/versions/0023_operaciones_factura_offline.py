"""idempotencia de operaciones offline sobre facturas

Cuando se agrega un ítem a una factura sin conexión, el POS guarda la operación
y la envía al volver la red. Si la respuesta se pierde, el reintento debe
devolver la factura sin agregar el producto otra vez. ``operaciones_factura_idempotentes``
guarda una fila única por operación.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operaciones_factura_idempotentes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clave", sa.String(length=64), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.String(length=32),
            server_default="agregar_item",
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["factura_id"], ["facturas.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_operaciones_factura_idempotentes_clave"),
        "operaciones_factura_idempotentes",
        ["clave"],
        unique=True,
    )
    op.create_index(
        op.f("ix_operaciones_factura_idempotentes_factura_id"),
        "operaciones_factura_idempotentes",
        ["factura_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_operaciones_factura_idempotentes_factura_id"),
        table_name="operaciones_factura_idempotentes",
    )
    op.drop_index(
        op.f("ix_operaciones_factura_idempotentes_clave"),
        table_name="operaciones_factura_idempotentes",
    )
    op.drop_table("operaciones_factura_idempotentes")
