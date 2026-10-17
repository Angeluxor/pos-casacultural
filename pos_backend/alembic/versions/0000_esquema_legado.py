"""esquema legado

Revisión base: reproduce el esquema que existía en producción creado con
`Base.metadata.create_all` antes de adoptar Alembic.

Refleja el estado REAL de esas bases, que **no** incluía:
- la columna `usuarios.token_version`, ni
- la FK `facturas.anulada_por_id -> usuarios.id`.

Ambas se añaden en la revisión siguiente (`0001_regularizacion`), de modo que
una base legada marcada con `alembic stamp 0000` queda al día tras
`alembic upgrade head`.

Revision ID: 0000
Revises:
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("documento", sa.String(), nullable=True),
        sa.Column("celular", sa.String(), nullable=True),
        sa.Column("correo", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clientes_documento"), "clientes", ["documento"], unique=True)
    op.create_index(op.f("ix_clientes_id"), "clientes", ["id"], unique=False)
    op.create_index(op.f("ix_clientes_nombre"), "clientes", ["nombre"], unique=False)

    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(), nullable=True),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("precio", sa.Float(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_productos_codigo"), "productos", ["codigo"], unique=True)
    op.create_index(op.f("ix_productos_id"), "productos", ["id"], unique=False)
    op.create_index(op.f("ix_productos_nombre"), "productos", ["nombre"], unique=False)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("rol", sa.Enum("ADMIN", "CAJERO", name="rolusuario"), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usuarios_id"), "usuarios", ["id"], unique=False)
    op.create_index(op.f("ix_usuarios_username"), "usuarios", ["username"], unique=True)

    op.create_table(
        "facturas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("vendedor_id", sa.Integer(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total", sa.Float(), nullable=True),
        sa.Column("saldo", sa.Float(), nullable=True),
        sa.Column("estado", sa.Enum("PENDIENTE", "PAGADO_PARCIAL", "PAGADA", "ANULADA", name="estadofactura"), nullable=True),
        sa.Column("anulada_por_id", sa.Integer(), nullable=True),
        sa.Column("motivo_anulacion", sa.String(), nullable=True),
        sa.Column("fecha_anulacion", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.ForeignKeyConstraint(["vendedor_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_facturas_id"), "facturas", ["id"], unique=False)

    op.create_table(
        "kardex",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tipo_movimiento",
            sa.Enum(
                "ENTRADA_COMPRA",
                "SALIDA_VENTA",
                "DEVOLUCION",
                "AJUSTE",
                name="tipomovimientoinventario",
            ),
            nullable=True,
        ),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column("saldo_stock", sa.Integer(), nullable=True),
        sa.Column("referencia", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kardex_id"), "kardex", ["id"], unique=False)

    op.create_table(
        "turnos_caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_apertura_id", sa.Integer(), nullable=True),
        sa.Column("usuario_cierre_id", sa.Integer(), nullable=True),
        sa.Column("fecha_apertura", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("saldo_inicial", sa.Float(), nullable=True),
        sa.Column("saldo_final_real", sa.Float(), nullable=True),
        sa.Column("abierta", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_apertura_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["usuario_cierre_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_turnos_caja_id"), "turnos_caja", ["id"], unique=False)

    op.create_table(
        "caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turno_caja_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tipo",
            sa.Enum("ENTRADA", "SALIDA", "APERTURA", "CIERRE", name="tipomovimientocaja"),
            nullable=True,
        ),
        sa.Column("referencia", sa.String(), nullable=True),
        sa.Column(
            "forma_pago",
            sa.Enum("EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", name="formapago"),
            nullable=True,
        ),
        sa.Column("monto", sa.Float(), nullable=True),
        sa.Column("observacion", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["turno_caja_id"], ["turnos_caja.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_caja_id"), "caja", ["id"], unique=False)

    op.create_table(
        "detalles_factura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=True),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column("precio_unitario", sa.Float(), nullable=True),
        sa.Column("subtotal", sa.Float(), nullable=True),
        sa.Column("anulado", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["factura_id"], ["facturas.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_detalles_factura_id"), "detalles_factura", ["id"], unique=False)

    op.create_table(
        "pagos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=True),
        sa.Column("cajero_id", sa.Integer(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column(
            "forma_pago",
            sa.Enum("EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", name="formapago"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["cajero_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["factura_id"], ["facturas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pagos_id"), "pagos", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pagos_id"), table_name="pagos")
    op.drop_table("pagos")
    op.drop_index(op.f("ix_detalles_factura_id"), table_name="detalles_factura")
    op.drop_table("detalles_factura")
    op.drop_index(op.f("ix_caja_id"), table_name="caja")
    op.drop_table("caja")
    op.drop_index(op.f("ix_turnos_caja_id"), table_name="turnos_caja")
    op.drop_table("turnos_caja")
    op.drop_index(op.f("ix_kardex_id"), table_name="kardex")
    op.drop_table("kardex")
    op.drop_index(op.f("ix_facturas_id"), table_name="facturas")
    op.drop_table("facturas")
    op.drop_index(op.f("ix_usuarios_username"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_id"), table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_index(op.f("ix_productos_nombre"), table_name="productos")
    op.drop_index(op.f("ix_productos_id"), table_name="productos")
    op.drop_index(op.f("ix_productos_codigo"), table_name="productos")
    op.drop_table("productos")
    op.drop_index(op.f("ix_clientes_nombre"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_id"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_documento"), table_name="clientes")
    op.drop_table("clientes")
    # Los ENUM se crean una sola vez (sin `create_type=False`) y, en Postgres,
    # sobreviven a `DROP TABLE`; hay que borrarlos explícitamente para poder
    # volver a aplicar `upgrade` (si no, falla con "type already exists").
    for tipo in ("formapago", "tipomovimientocaja", "tipomovimientoinventario", "estadofactura", "rolusuario"):
        op.execute(f"DROP TYPE IF EXISTS {tipo}")
