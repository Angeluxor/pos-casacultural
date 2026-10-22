"""idempotencia en el registro de pagos

Un cobro puede incluir varios medios de pago, así que la clave de idempotencia
no se guarda en ``pagos`` (se repetiría). Se crea ``pagos_idempotentes`` con una
fila única por solicitud: si el navegador reintenta tras un timeout, el backend
devuelve la factura sin volver a insertar pagos ni movimientos de caja.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pagos_idempotentes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clave", sa.String(length=64), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
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
        op.f("ix_pagos_idempotentes_clave"),
        "pagos_idempotentes",
        ["clave"],
        unique=True,
    )
    op.create_index(
        op.f("ix_pagos_idempotentes_factura_id"),
        "pagos_idempotentes",
        ["factura_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pagos_idempotentes_factura_id"),
        table_name="pagos_idempotentes",
    )
    op.drop_index(
        op.f("ix_pagos_idempotentes_clave"), table_name="pagos_idempotentes"
    )
    op.drop_table("pagos_idempotentes")
