"""motivo de ajuste en el kardex

Añade a `kardex` los campos usados por los ajustes manuales de stock:

- `motivo` (tipo `motivoajuste`: DERRAMA / MAL_CONTEO / OTRO);
- `motivo_detalle` (texto libre, obligatorio cuando el motivo es OTRO).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALORES_MOTIVO = ("DERRAMA", "MAL_CONTEO", "OTRO")


def upgrade() -> None:
    motivo = postgresql.ENUM(*_VALORES_MOTIVO, name="motivoajuste")
    motivo.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "kardex",
        sa.Column(
            "motivo",
            postgresql.ENUM(*_VALORES_MOTIVO, name="motivoajuste", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("kardex", sa.Column("motivo_detalle", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("kardex", "motivo_detalle")
    op.drop_column("kardex", "motivo")
    postgresql.ENUM(*_VALORES_MOTIVO, name="motivoajuste").drop(
        op.get_bind(), checkfirst=True
    )
