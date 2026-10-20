"""cuentas por pagar y balance general

Agrega a ``ingresos_inventario`` el control de pago de las compras a crédito:

- ``pagado``: las compras de contado y las donaciones nacen pagadas; las
  compras a crédito nacen pendientes.
- ``fecha_pago``, ``pagado_por_id`` y ``forma_pago_pago``: trazabilidad del
  pago (quién, cuándo y con qué forma de pago).

Las compras a crédito existentes quedan como pendientes, porque el sistema
anterior no registraba su pago. Las compras de contado/transferencia existentes
se marcan como pagadas y se les copia la fecha del ingreso.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALORES_FORMA_PAGO = ("EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", "NOMINA")


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"
    forma_pago_pago = (
        postgresql.ENUM(*_VALORES_FORMA_PAGO, name="formapago", create_type=False)
        if es_postgres
        else sa.String()
    )

    op.add_column(
        "ingresos_inventario",
        sa.Column("pagado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("fecha_pago", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("pagado_por_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ingresos_inventario",
        sa.Column("forma_pago_pago", forma_pago_pago, nullable=True),
    )
    op.create_index(
        op.f("ix_ingresos_inventario_pagado_por_id"),
        "ingresos_inventario",
        ["pagado_por_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_ingresos_inventario_pagado_por_id",
        "ingresos_inventario",
        "usuarios",
        ["pagado_por_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if es_postgres:
        op.execute(
            """
            UPDATE ingresos_inventario
            SET pagado = (COALESCE(forma_pago::text, '') <> 'CREDITO'),
                fecha_pago = CASE
                    WHEN forma_pago IN ('EFECTIVO', 'TRANSFERENCIA') THEN fecha
                    ELSE NULL
                END,
                pagado_por_id = CASE
                    WHEN forma_pago IN ('EFECTIVO', 'TRANSFERENCIA') THEN usuario_id
                    ELSE NULL
                END,
                forma_pago_pago = CASE
                    WHEN forma_pago = 'EFECTIVO' THEN 'EFECTIVO'::formapago
                    WHEN forma_pago = 'TRANSFERENCIA' THEN 'TRANSFERENCIA'::formapago
                    ELSE NULL
                END
            """
        )
    else:
        op.execute(
            """
            UPDATE ingresos_inventario
            SET pagado = CASE WHEN forma_pago = 'CREDITO' THEN 0 ELSE 1 END,
                fecha_pago = CASE
                    WHEN forma_pago IN ('EFECTIVO', 'TRANSFERENCIA') THEN fecha
                    ELSE NULL
                END,
                pagado_por_id = CASE
                    WHEN forma_pago IN ('EFECTIVO', 'TRANSFERENCIA') THEN usuario_id
                    ELSE NULL
                END,
                forma_pago_pago = CASE
                    WHEN forma_pago IN ('EFECTIVO', 'TRANSFERENCIA') THEN forma_pago
                    ELSE NULL
                END
            """
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ingresos_inventario_pagado_por_id",
        "ingresos_inventario",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_ingresos_inventario_pagado_por_id"),
        table_name="ingresos_inventario",
    )
    op.drop_column("ingresos_inventario", "forma_pago_pago")
    op.drop_column("ingresos_inventario", "pagado_por_id")
    op.drop_column("ingresos_inventario", "fecha_pago")
    op.drop_column("ingresos_inventario", "pagado")
