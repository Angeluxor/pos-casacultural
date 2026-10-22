"""metadatos para ventas sincronizadas desde el modo offline

``origen`` distingue una venta creada en línea de una que se guardó en el
dispositivo y se sincronizó después. ``requiere_revision`` marca las ventas
offline que dejaron stock negativo o que se asociaron a un turno ya cerrado,
para que el negocio las revise sin perder la venta.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "facturas",
        sa.Column(
            "origen",
            sa.String(length=16),
            server_default="online",
            nullable=False,
        ),
    )
    op.add_column(
        "facturas",
        sa.Column(
            "requiere_revision",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "facturas",
        sa.Column("nota_revision", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_facturas_requiere_revision"),
        "facturas",
        ["requiere_revision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_facturas_requiere_revision"), table_name="facturas"
    )
    op.drop_column("facturas", "nota_revision")
    op.drop_column("facturas", "requiere_revision")
    op.drop_column("facturas", "origen")
