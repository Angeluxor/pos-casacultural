"""protege la relación facturas-cliente

Recrea la FK ``facturas.cliente_id -> clientes.id`` con ``ON DELETE RESTRICT``.
Así la propia base de datos impide borrar un cliente que tenga ventas, aunque
la comprobación de la aplicación fallara o se ejecutara SQL directo.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombre_fk_cliente() -> str | None:
    """Nombre real de la FK facturas.cliente_id -> clientes.id.

    En bases creadas por `create_all` o por la revisión 0000 el nombre lo pone
    PostgreSQL (`facturas_cliente_id_fkey`), pero se consulta en vez de
    asumirlo para tolerar bases con otro nombre.
    """
    inspector = inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("facturas"):
        if (
            fk.get("constrained_columns") == ["cliente_id"]
            and fk.get("referred_table") == "clientes"
        ):
            return fk.get("name")
    return None


def upgrade() -> None:
    nombre = _nombre_fk_cliente()
    if nombre:
        op.drop_constraint(nombre, "facturas", type_="foreignkey")
    op.create_foreign_key(
        "fk_facturas_cliente_id",
        "facturas",
        "clientes",
        ["cliente_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_facturas_cliente_id", "facturas", type_="foreignkey")
    op.create_foreign_key(
        "facturas_cliente_id_fkey",
        "facturas",
        "clientes",
        ["cliente_id"],
        ["id"],
    )
