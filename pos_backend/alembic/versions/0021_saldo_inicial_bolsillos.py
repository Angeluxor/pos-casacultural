"""saldo inicial de bolsillos sin descontar caja/banco

Agrega ``bolsillo_movimientos.es_inicial``. Un aporte marcado como inicial
suma al saldo del bolsillo pero no se descuenta del efectivo/banco: representa
dinero que ya estaba apartado antes de empezar a usar la aplicación.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bolsillo_movimientos") as batch:
        batch.add_column(
            sa.Column(
                "es_inicial",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("bolsillo_movimientos") as batch:
        batch.drop_column("es_inicial")
