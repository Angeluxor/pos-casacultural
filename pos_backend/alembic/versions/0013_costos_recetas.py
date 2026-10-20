"""costos: recetas de preparaciones y costos manuales

Agrega el módulo de costos:

- ``productos.misma_unidad_compra_venta``: marca los productos que se compran
  y venden en la misma unidad, para comparar su costo con el precio de venta.
- ``recetas`` / ``receta_items``: receta estándar de un producto transformado,
  con su rendimiento y los insumos que la componen.
- ``costos_manuales``: costos unitarios registrados a mano para insumos que no
  tienen compras, o para corregir el costo vigente.

Las recetas no mueven inventario: solo calculan costo.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Los productos existentes se consideran 1:1 por defecto; el usuario puede
    # desmarcarlos desde Productos si compra por caja/paquete y vende por unidad.
    with op.batch_alter_table("productos") as batch:
        batch.add_column(
            sa.Column(
                "misma_unidad_compra_venta",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )

    op.create_table(
        "recetas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("rendimiento", sa.Float(), nullable=False),
        sa.Column("notas", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recetas_id"), "recetas", ["id"], unique=False)
    op.create_index(
        op.f("ix_recetas_producto_id"), "recetas", ["producto_id"], unique=True
    )

    op.create_table(
        "receta_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receta_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["receta_id"], ["recetas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receta_id", "producto_id", name="uq_receta_items_receta_producto"
        ),
    )
    op.create_index(op.f("ix_receta_items_id"), "receta_items", ["id"], unique=False)
    op.create_index(
        op.f("ix_receta_items_producto_id"),
        "receta_items",
        ["producto_id"],
        unique=False,
    )

    op.create_table(
        "costos_manuales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("costo_unitario", sa.Float(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_costos_manuales_id"), "costos_manuales", ["id"], unique=False
    )
    op.create_index(
        "ix_costos_manuales_producto_fecha",
        "costos_manuales",
        ["producto_id", "fecha"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_costos_manuales_producto_fecha", table_name="costos_manuales"
    )
    op.drop_index(op.f("ix_costos_manuales_id"), table_name="costos_manuales")
    op.drop_table("costos_manuales")

    op.drop_index(op.f("ix_receta_items_producto_id"), table_name="receta_items")
    op.drop_index(op.f("ix_receta_items_id"), table_name="receta_items")
    op.drop_table("receta_items")

    op.drop_index(op.f("ix_recetas_producto_id"), table_name="recetas")
    op.drop_index(op.f("ix_recetas_id"), table_name="recetas")
    op.drop_table("recetas")

    with op.batch_alter_table("productos") as batch:
        batch.drop_column("misma_unidad_compra_venta")
