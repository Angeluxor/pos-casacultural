"""auditoría de descuentos de nómina

Crea ``descuentos_nomina``: un evento por cada descuento aplicado, con una foto
del empleado, el cliente, el admin que lo aplicó, el monto, el saldo resultante
y una nota/periodo. Cada ``pago`` por nómina queda enlazado al evento, de modo
que un descuento que toca varias facturas se puede auditar como una sola
operación.

Los datos existentes (si ya se habían aplicado descuentos de nómina antes de
esta revisión) se migran como eventos individuales por pago, con la nota
"Registro migrado"; no es posible reconstruir la agrupación original.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_descuentos(bind) -> None:
    """Convierte los pagos Nómina existentes en eventos de auditoría."""
    if bind.dialect.name != "postgresql":
        return
    filas = bind.execute(
        sa.text(
            """
            SELECT p.id AS pago_id, COALESCE(p.fecha, NOW()) AS fecha,
                   COALESCE(p.valor, 0) AS valor, p.cajero_id,
                   f.cliente_id, COALESCE(f.saldo, 0) AS factura_saldo,
                   c.nombre AS cliente_nombre,
                   u.id AS usuario_id, u.nombre AS usuario_nombre,
                   r.nombre AS registrado_por_nombre
            FROM pagos p
            JOIN facturas f ON f.id = p.factura_id
            LEFT JOIN clientes c ON c.id = f.cliente_id
            LEFT JOIN usuarios u ON u.cliente_id = f.cliente_id
            LEFT JOIN usuarios r ON r.id = p.cajero_id
            WHERE p.forma_pago = 'NOMINA' AND p.descuento_nomina_id IS NULL
            ORDER BY p.fecha, p.id
            """
        )
    ).mappings().all()

    for fila in filas:
        nuevo_id = bind.execute(
            sa.text(
                """
                INSERT INTO descuentos_nomina (
                    usuario_id, usuario_nombre, cliente_id, cliente_nombre,
                    registrado_por_id, registrado_por_nombre, fecha, monto,
                    saldo_pendiente, facturas_afectadas, nota
                ) VALUES (
                    :usuario_id, :usuario_nombre, :cliente_id, :cliente_nombre,
                    :registrado_por_id, :registrado_por_nombre, :fecha, :monto,
                    :saldo_pendiente, 1, 'Registro migrado'
                )
                RETURNING id
                """
            ),
            {
                "usuario_id": fila["usuario_id"],
                "usuario_nombre": fila["usuario_nombre"] or "Empleado no identificado",
                "cliente_id": fila["cliente_id"],
                "cliente_nombre": fila["cliente_nombre"] or "Cliente no identificado",
                "registrado_por_id": fila["cajero_id"],
                "registrado_por_nombre": fila["registrado_por_nombre"] or "—",
                "fecha": fila["fecha"],
                "monto": fila["valor"],
                "saldo_pendiente": fila["factura_saldo"] or 0,
            },
        ).scalar_one()
        bind.execute(
            sa.text(
                "UPDATE pagos SET descuento_nomina_id = :nuevo "
                "WHERE id = :pago"
            ),
            {"nuevo": nuevo_id, "pago": fila["pago_id"]},
        )


def upgrade() -> None:
    op.create_table(
        "descuentos_nomina",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("cliente_nombre", sa.String(), nullable=False),
        sa.Column("registrado_por_id", sa.Integer(), nullable=True),
        sa.Column("registrado_por_nombre", sa.String(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monto", sa.Float(), nullable=False),
        sa.Column("saldo_pendiente", sa.Float(), nullable=False),
        sa.Column("facturas_afectadas", sa.Integer(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_descuentos_nomina_usuario_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cliente_id"],
            ["clientes.id"],
            name="fk_descuentos_nomina_cliente_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por_id"],
            ["usuarios.id"],
            name="fk_descuentos_nomina_registrado_por_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_descuentos_nomina_id"), "descuentos_nomina", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_descuentos_nomina_usuario_id"),
        "descuentos_nomina",
        ["usuario_id"],
        unique=False,
    )

    op.add_column(
        "pagos", sa.Column("descuento_nomina_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_pagos_descuento_nomina_id"),
        "pagos",
        ["descuento_nomina_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_pagos_descuento_nomina_id",
        "pagos",
        "descuentos_nomina",
        ["descuento_nomina_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _backfill_descuentos(op.get_bind())


def downgrade() -> None:
    op.drop_constraint(
        "fk_pagos_descuento_nomina_id", "pagos", type_="foreignkey"
    )
    op.drop_index(op.f("ix_pagos_descuento_nomina_id"), table_name="pagos")
    op.drop_column("pagos", "descuento_nomina_id")

    op.drop_index(
        op.f("ix_descuentos_nomina_usuario_id"), table_name="descuentos_nomina"
    )
    op.drop_index(op.f("ix_descuentos_nomina_id"), table_name="descuentos_nomina")
    op.drop_table("descuentos_nomina")
