"""caja desdoblada en efectivo y banco

- `turnos_caja`: se reemplazan `saldo_inicial` y `saldo_final_real` por los
  pares `saldo_inicial_efectivo` / `saldo_inicial_banco` y
  `saldo_final_real_efectivo` / `saldo_final_real_banco`. El turno histórico
  migra con 0 en ambos bolsillos (el desglose original no se registraba).
- `caja.forma_pago`: pasa a ser obligatoria (`NOT NULL`). Los movimientos
  legados sin forma de pago se registran como EFECTIVO.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "turnos_caja",
        sa.Column(
            "saldo_inicial_efectivo",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "turnos_caja",
        sa.Column(
            "saldo_inicial_banco",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "turnos_caja", sa.Column("saldo_final_real_efectivo", sa.Float(), nullable=True)
    )
    op.add_column(
        "turnos_caja", sa.Column("saldo_final_real_banco", sa.Float(), nullable=True)
    )
    # Se retiran los `server_default` para que el esquema coincida con el modelo.
    op.alter_column("turnos_caja", "saldo_inicial_efectivo", server_default=None)
    op.alter_column("turnos_caja", "saldo_inicial_banco", server_default=None)

    op.drop_column("turnos_caja", "saldo_final_real")
    op.drop_column("turnos_caja", "saldo_inicial")

    # Los movimientos de caja legados sin forma de pago se asumen en efectivo.
    op.execute("UPDATE caja SET forma_pago = 'EFECTIVO' WHERE forma_pago IS NULL")
    op.alter_column(
        "caja",
        "forma_pago",
        existing_type=postgresql.ENUM(
            "EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", name="formapago"
        ),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "caja",
        "forma_pago",
        existing_type=postgresql.ENUM(
            "EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO", name="formapago"
        ),
        nullable=True,
    )

    op.add_column("turnos_caja", sa.Column("saldo_inicial", sa.Float(), nullable=True))
    op.add_column(
        "turnos_caja", sa.Column("saldo_final_real", sa.Float(), nullable=True)
    )
    op.execute(
        "UPDATE turnos_caja "
        "SET saldo_inicial = saldo_inicial_efectivo + saldo_inicial_banco, "
        "saldo_final_real = COALESCE(saldo_final_real_efectivo, 0) "
        "+ COALESCE(saldo_final_real_banco, 0)"
    )
    op.drop_column("turnos_caja", "saldo_final_real_banco")
    op.drop_column("turnos_caja", "saldo_final_real_efectivo")
    op.drop_column("turnos_caja", "saldo_inicial_banco")
    op.drop_column("turnos_caja", "saldo_inicial_efectivo")
