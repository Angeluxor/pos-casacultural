"""formatos de compra en los ingresos de inventario

Permite registrar una compra por caja o paquete indicando cuántas unidades
trae el formato y cuál es su costo. El ingreso guarda la cantidad total en
unidades (que es la que mueve el stock) y conserva los datos del formato para
mostrar y auditar cómo se digitó la compra.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingresos_inventario_items",
        sa.Column("cantidad_formatos", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ingresos_inventario_items",
        sa.Column("unidades_por_formato", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ingresos_inventario_items",
        sa.Column("costo_formato", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingresos_inventario_items", "costo_formato")
    op.drop_column("ingresos_inventario_items", "unidades_por_formato")
    op.drop_column("ingresos_inventario_items", "cantidad_formatos")
