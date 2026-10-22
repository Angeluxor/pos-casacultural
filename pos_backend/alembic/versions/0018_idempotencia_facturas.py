"""idempotencia en la creación de ventas

Añade ``facturas.clave_idempotencia``. El cliente envía una clave única en la
cabecera ``Idempotency-Key``; si la petición se reintenta tras un timeout, el
backend devuelve la venta original en lugar de crear otra y volver a descontar
stock.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "facturas",
        sa.Column("clave_idempotencia", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_facturas_clave_idempotencia"),
        "facturas",
        ["clave_idempotencia"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_facturas_clave_idempotencia"), table_name="facturas"
    )
    op.drop_column("facturas", "clave_idempotencia")
