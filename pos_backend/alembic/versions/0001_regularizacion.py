"""regularización del esquema

Añade los elementos que faltaban en las bases legadas (revisión `0000`):

- columna `usuarios.token_version` (`Integer NOT NULL DEFAULT 0`), usada para
  invalidar los JWT al cerrar sesión o cambiar la contraseña;
- FK `facturas.anulada_por_id -> usuarios.id`.

En una base nueva (`0000` + esta revisión) el esquema final es idéntico al de
los modelos. En una base legada, `alembic stamp 0000` + `alembic upgrade head`
repara exactamente estas diferencias.

Revision ID: 0001
Revises: 0000
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = "0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    # Se retira el `server_default` para que el esquema coincida con el modelo
    # (que solo define un default a nivel de Python).
    op.alter_column("usuarios", "token_version", server_default=None)

    op.create_foreign_key(None, "facturas", "usuarios", ["anulada_por_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("facturas_anulada_por_id_fkey", "facturas", type_="foreignkey")
    op.drop_column("usuarios", "token_version")
