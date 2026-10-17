"""facturas: estado Abierta/Crédito y cliente eventual

Ajusta el módulo de facturas/ventas:

- El estado de factura deja de ser ``Pendiente`` y pasa a ``Abierta``; se agrega
  ``Crédito`` (deuda del cliente) que reemplaza el saldo que quedaba al cerrar
  caja. Las facturas viejas ``Pendiente``/``Pagado Parcial`` se migran a
  ``Crédito`` porque no se cobraron al cierre.
- ``facturas.turno_caja_id``: turno de caja en el que se registró la venta.
- ``facturas.nombre_eventual``: nombre temporal que da el cajero cuando el
  cliente no se registra (solo texto).
- ``clientes.es_eventual`` y el único registro genérico "Cliente eventual"
  (reemplaza al antiguo "Consumidor final"). Las facturas sin cliente se
  reasignan a este registro.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Orden de valores igual al del enum en `app/db/models.py` (SQLAlchemy guarda
# los NOMBRES de miembro).
_VALORES_NUEVOS = ("ABIERTA", "PAGADO_PARCIAL", "PAGADA", "CREDITO", "ANULADA")
_VALORES_VIEJOS = ("PENDIENTE", "PAGADO_PARCIAL", "PAGADA", "ANULADA")


def upgrade() -> None:
    # --- Columnas nuevas ---
    op.add_column(
        "clientes",
        sa.Column("es_eventual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("clientes", "es_eventual", server_default=None)
    op.add_column("facturas", sa.Column("turno_caja_id", sa.Integer(), nullable=True))
    op.add_column("facturas", sa.Column("nombre_eventual", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_facturas_turno_caja", "facturas", "turnos_caja", ["turno_caja_id"], ["id"]
    )

    # --- Recrear el tipo enumerado con los valores nuevos ---
    #
    # Se recrea el tipo (en vez de ALTER TYPE ... ADD VALUE) porque PostgreSQL
    # no deja usar un valor recién agregado dentro de la misma transacción.
    # El alias de datos mapea las facturas viejas Pendiente/Pagado Parcial a
    # Crédito, según lo pedido.
    op.execute("ALTER TABLE facturas ALTER COLUMN estado DROP DEFAULT")
    valores = ", ".join(f"'{v}'" for v in _VALORES_NUEVOS)
    op.execute(f"CREATE TYPE estadofactura_new AS ENUM ({valores})")
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN estado TYPE estadofactura_new USING ("
        "  CASE estado::text"
        "    WHEN 'PAGADA' THEN 'PAGADA'"
        "    WHEN 'ANULADA' THEN 'ANULADA'"
        "    ELSE 'CREDITO'"
        "  END"
        ")::estadofactura_new"
    )
    op.execute("DROP TYPE estadofactura")
    op.execute("ALTER TYPE estadofactura_new RENAME TO estadofactura")

    # --- Cliente genérico "Cliente eventual" ---
    op.execute(
        "INSERT INTO clientes (nombre, es_eventual) "
        "SELECT 'Cliente eventual', true "
        "WHERE NOT EXISTS (SELECT 1 FROM clientes WHERE es_eventual = true)"
    )
    # Las facturas sin cliente (antes "Consumidor final") pasan al cliente eventual.
    op.execute(
        "UPDATE facturas SET cliente_id = "
        "(SELECT id FROM clientes WHERE es_eventual = true ORDER BY id LIMIT 1) "
        "WHERE cliente_id IS NULL"
    )


def downgrade() -> None:
    # Deshacer el paso a cliente eventual.
    op.execute(
        "UPDATE facturas SET cliente_id = NULL "
        "WHERE cliente_id IN (SELECT id FROM clientes WHERE es_eventual = true)"
    )
    op.execute("DELETE FROM clientes WHERE es_eventual = true")

    op.drop_constraint("fk_facturas_turno_caja", "facturas", type_="foreignkey")
    op.drop_column("facturas", "nombre_eventual")
    op.drop_column("facturas", "turno_caja_id")
    op.drop_column("clientes", "es_eventual")

    # Volver al tipo enumerado anterior (Crédito -> Pendiente).
    op.execute("ALTER TABLE facturas ALTER COLUMN estado DROP DEFAULT")
    valores = ", ".join(f"'{v}'" for v in _VALORES_VIEJOS)
    op.execute(f"CREATE TYPE estadofactura_old AS ENUM ({valores})")
    op.execute(
        "ALTER TABLE facturas ALTER COLUMN estado TYPE estadofactura_old USING ("
        "  CASE estado::text"
        "    WHEN 'ABIERTA' THEN 'PENDIENTE'"
        "    WHEN 'CREDITO' THEN 'PENDIENTE'"
        "    ELSE estado::text"
        "  END"
        ")::estadofactura_old"
    )
    op.execute("DROP TYPE estadofactura")
    op.execute("ALTER TYPE estadofactura_old RENAME TO estadofactura")
