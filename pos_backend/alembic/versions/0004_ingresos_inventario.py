"""ingresos de inventario

Crea el módulo de ingresos de inventario:

- `ingresos_inventario`: cabecera (fecha, usuario, proveedor, forma de pago,
  total declarado e inmutable, estado y justificación de resolución);
- `ingresos_inventario_items`: líneas del ingreso (producto existente,
  producto nuevo o ítem "Otros");
- tipos `formapagoingreso`, `estadoingreso` y `tipoitemingreso`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALORES_FORMA_PAGO = ("EFECTIVO", "TRANSFERENCIA", "CREDITO", "DONACION")
_VALORES_ESTADO = ("COMPLETO", "PARCIAL", "INCONSISTENTE")
_VALORES_TIPO_ITEM = ("PRODUCTO", "PRODUCTO_NUEVO", "OTROS")


def upgrade() -> None:
    forma_pago = postgresql.ENUM(*_VALORES_FORMA_PAGO, name="formapagoingreso")
    estado = postgresql.ENUM(*_VALORES_ESTADO, name="estadoingreso")
    tipo_item = postgresql.ENUM(*_VALORES_TIPO_ITEM, name="tipoitemingreso")
    for tipo in (forma_pago, estado, tipo_item):
        tipo.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ingresos_inventario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("turno_caja_id", sa.Integer(), nullable=True),
        sa.Column("proveedor", sa.String(), nullable=True),
        sa.Column(
            "forma_pago",
            postgresql.ENUM(*_VALORES_FORMA_PAGO, name="formapagoingreso", create_type=False),
            nullable=True,
        ),
        sa.Column("total", sa.Float(), nullable=True),
        sa.Column(
            "estado",
            postgresql.ENUM(*_VALORES_ESTADO, name="estadoingreso", create_type=False),
            nullable=True,
        ),
        sa.Column("justificacion", sa.String(), nullable=True),
        sa.Column("observacion", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["turno_caja_id"], ["turnos_caja.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingresos_inventario_id"), "ingresos_inventario", ["id"], unique=False
    )

    op.create_table(
        "ingresos_inventario_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingreso_id", sa.Integer(), nullable=True),
        sa.Column(
            "tipo",
            postgresql.ENUM(*_VALORES_TIPO_ITEM, name="tipoitemingreso", create_type=False),
            nullable=True,
        ),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("concepto", sa.String(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column("costo_unitario", sa.Float(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["ingreso_id"], ["ingresos_inventario.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingresos_inventario_items_id"),
        "ingresos_inventario_items",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ingresos_inventario_items_id"), table_name="ingresos_inventario_items"
    )
    op.drop_table("ingresos_inventario_items")
    op.drop_index(op.f("ix_ingresos_inventario_id"), table_name="ingresos_inventario")
    op.drop_table("ingresos_inventario")
    for tipo in ("tipoitemingreso", "estadoingreso", "formapagoingreso"):
        op.execute(f"DROP TYPE IF EXISTS {tipo}")