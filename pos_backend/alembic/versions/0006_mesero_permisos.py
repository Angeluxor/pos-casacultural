"""rol Mesero y permisos configurables por rol

- Agrega el valor ``MESERO`` al tipo enumerado ``rolusuario``. En PostgreSQL se
  recrea el tipo (como en la revisión ``0005``) porque ``ALTER TYPE ... ADD
  VALUE`` no permite usar el valor nuevo dentro de la misma transacción.
- Crea la tabla ``permisos_rol`` con los permisos configurados para los roles
  ``Cajero`` y ``Mesero`` (el ``Admin`` siempre tiene todos, no se guarda).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recrear_enum_rol(valores: Sequence[str], mapeo: str) -> None:
    """Recrea el tipo ``rolusuario`` con otro conjunto de valores.

    ``mapeo`` es la expresión SQL que convierte el valor actual al nuevo.
    """
    op.execute("ALTER TABLE usuarios ALTER COLUMN rol DROP DEFAULT")
    lista = ", ".join(f"'{v}'" for v in valores)
    op.execute(f"CREATE TYPE rolusuario_new AS ENUM ({lista})")
    op.execute(
        "ALTER TABLE usuarios ALTER COLUMN rol TYPE rolusuario_new "
        f"USING ({mapeo})::rolusuario_new"
    )
    op.execute("DROP TYPE rolusuario")
    op.execute("ALTER TYPE rolusuario_new RENAME TO rolusuario")


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    if es_postgres:
        _recrear_enum_rol(("ADMIN", "CAJERO", "MESERO"), "rol::text")

    rol_col = (
        postgresql.ENUM("ADMIN", "CAJERO", "MESERO", name="rolusuario", create_type=False)
        if es_postgres
        else sa.String()
    )

    op.create_table(
        "permisos_rol",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rol", rol_col, nullable=False),
        sa.Column("permisos", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permisos_rol_id"), "permisos_rol", ["id"], unique=False)
    op.create_index("ix_permisos_rol_rol", "permisos_rol", ["rol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_permisos_rol_rol", table_name="permisos_rol")
    op.drop_index(op.f("ix_permisos_rol_id"), table_name="permisos_rol")
    op.drop_table("permisos_rol")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _recrear_enum_rol(
            ("ADMIN", "CAJERO"),
            "CASE rol::text WHEN 'MESERO' THEN 'CAJERO' ELSE rol::text END",
        )
