"""proveedores: catálogo con FK desde los ingresos de inventario

Hasta ahora cada ingreso guardaba el proveedor como texto libre en
``ingresos_inventario.proveedor``. Esta revisión crea la tabla ``proveedores``,
traslada a ella los nombres ya registrados (sin duplicar espacios ni repetidos
exactos) y enlaza cada ingreso con su proveedor mediante ``proveedor_id``.
Después elimina la columna de texto para que el catálogo sea la única fuente de
verdad.

Los ingresos que no tenían proveedor quedan con ``proveedor_id`` nulo.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "proveedores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("documento", sa.String(), nullable=True),
        sa.Column("celular", sa.String(), nullable=True),
        sa.Column("correo", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proveedores_id"), "proveedores", ["id"], unique=False)
    op.create_index(
        op.f("ix_proveedores_nombre"), "proveedores", ["nombre"], unique=False
    )
    op.create_index(
        op.f("ix_proveedores_documento"),
        "proveedores",
        ["documento"],
        unique=True,
    )

    # Trasladar los nombres que ya estaban guardados como texto libre. Se
    # agrupa sin distinguir mayúsculas ni espacios para no crear duplicados.
    nombres = bind.execute(
        sa.text(
            """
            SELECT MIN(TRIM(proveedor)) AS nombre
            FROM ingresos_inventario
            WHERE proveedor IS NOT NULL AND TRIM(proveedor) <> ''
            GROUP BY LOWER(TRIM(proveedor))
            """
        )
    ).fetchall()
    for (nombre,) in nombres:
        bind.execute(
            sa.text("INSERT INTO proveedores (nombre) VALUES (:nombre)"),
            {"nombre": nombre},
        )

    # Agregar la FK (batch también funciona en SQLite, que no soporta
    # ALTER TABLE ADD CONSTRAINT).
    with op.batch_alter_table("ingresos_inventario") as batch:
        batch.add_column(sa.Column("proveedor_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ingresos_inventario_proveedor_id",
            "proveedores",
            ["proveedor_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind.execute(
        sa.text(
            """
            UPDATE ingresos_inventario
            SET proveedor_id = (
                SELECT p.id
                FROM proveedores p
                WHERE LOWER(p.nombre) = LOWER(TRIM(ingresos_inventario.proveedor))
            )
            WHERE proveedor IS NOT NULL AND TRIM(proveedor) <> ''
            """
        )
    )

    # Ya enlazados, el texto libre deja de ser necesario.
    with op.batch_alter_table("ingresos_inventario") as batch:
        batch.drop_column("proveedor")

    op.create_index(
        op.f("ix_ingresos_inventario_proveedor_id"),
        "ingresos_inventario",
        ["proveedor_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(
        op.f("ix_ingresos_inventario_proveedor_id"),
        table_name="ingresos_inventario",
    )

    with op.batch_alter_table("ingresos_inventario") as batch:
        batch.add_column(sa.Column("proveedor", sa.String(), nullable=True))

    # Recuperar el nombre para conservar la información si se revierte.
    bind.execute(
        sa.text(
            """
            UPDATE ingresos_inventario
            SET proveedor = (
                SELECT p.nombre
                FROM proveedores p
                WHERE p.id = ingresos_inventario.proveedor_id
            )
            WHERE proveedor_id IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("ingresos_inventario") as batch:
        batch.drop_constraint(
            "fk_ingresos_inventario_proveedor_id", type_="foreignkey"
        )
        batch.drop_column("proveedor_id")

    op.drop_index(op.f("ix_proveedores_nombre"), table_name="proveedores")
    op.drop_index(op.f("ix_proveedores_documento"), table_name="proveedores")
    op.drop_index(op.f("ix_proveedores_id"), table_name="proveedores")
    op.drop_table("proveedores")
