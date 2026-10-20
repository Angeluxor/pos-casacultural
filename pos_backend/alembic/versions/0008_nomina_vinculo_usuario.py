"""vínculo usuario-cliente y pago por nómina

- ``usuarios.cliente_id``: vínculo uno a uno entre un usuario del sistema y un
  cliente, para poder descontar de la nómina las compras a crédito. La columna
  es única (un cliente no puede quedar en dos usuarios) y usa
  ``ON DELETE SET NULL`` como red de seguridad si el cliente se elimina.
- Se agrega el valor ``NOMINA`` al tipo enumerado ``formapago``. Se recrea el
  tipo (como en las revisiones 0005/0006) porque PostgreSQL no permite usar un
  valor recién agregado dentro de la misma transacción.

La nómina no genera movimientos de caja: es una compensación, no un cobro.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALORES_NUEVOS = ("EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", "NOMINA")
_VALORES_VIEJOS = ("EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO")


def _recrear_enum_formapago(valores: Sequence[str], mapeo: str) -> None:
    """Recrea el tipo ``formapago`` (compartido por ``pagos`` y ``caja``)."""
    op.execute("ALTER TABLE pagos ALTER COLUMN forma_pago DROP DEFAULT")
    op.execute("ALTER TABLE caja ALTER COLUMN forma_pago DROP DEFAULT")
    lista = ", ".join(f"'{v}'" for v in valores)
    op.execute(f"CREATE TYPE formapago_new AS ENUM ({lista})")
    op.execute(
        "ALTER TABLE pagos ALTER COLUMN forma_pago TYPE formapago_new "
        f"USING ({mapeo})::formapago_new"
    )
    op.execute(
        "ALTER TABLE caja ALTER COLUMN forma_pago TYPE formapago_new "
        f"USING ({mapeo})::formapago_new"
    )
    op.execute("DROP TYPE formapago")
    op.execute("ALTER TYPE formapago_new RENAME TO formapago")


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_usuarios_cliente_id"), "usuarios", ["cliente_id"], unique=True
    )
    op.create_foreign_key(
        "fk_usuarios_cliente_id",
        "usuarios",
        "clientes",
        ["cliente_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if op.get_bind().dialect.name == "postgresql":
        _recrear_enum_formapago(_VALORES_NUEVOS, "forma_pago::text")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _recrear_enum_formapago(
            _VALORES_VIEJOS,
            "CASE forma_pago::text WHEN 'NOMINA' THEN 'OTRO' ELSE forma_pago::text END",
        )

    op.drop_constraint("fk_usuarios_cliente_id", "usuarios", type_="foreignkey")
    op.drop_index(op.f("ix_usuarios_cliente_id"), table_name="usuarios")
    op.drop_column("usuarios", "cliente_id")
