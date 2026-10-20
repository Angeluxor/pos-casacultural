"""fuente de pago del ingreso: caja activa o balance general

Agrega ``ingresos_inventario.fuente_pago`` para distinguir los ingresos que se
registran contra la caja abierta de los que se cargan directamente al balance
general (compras ya pagadas por fuera o saldos iniciales).

Los ingresos existentes quedan como ``CAJA`` si tienen turno asociado y como
``BALANCE`` si no lo tienen. El modo balance no mueve caja ni exige un turno
abierto; las compras a crédito registradas así siguen siendo cuentas por pagar.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALORES_FUENTE = ("CAJA", "BALANCE")


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    if es_postgres:
        # Se crea el tipo antes de agregar la columna para que ALTER TABLE lo
        # encuentre; ``checkfirst`` permite reintentar si quedó de un intento
        # anterior.
        postgresql.ENUM(*_VALORES_FUENTE, name="fuente_pago_ingreso").create(
            bind, checkfirst=True
        )
        fuente = postgresql.ENUM(
            *_VALORES_FUENTE, name="fuente_pago_ingreso", create_type=False
        )
    else:
        fuente = sa.String()

    op.add_column(
        "ingresos_inventario",
        sa.Column(
            "fuente_pago",
            fuente,
            nullable=False,
            server_default="CAJA",
        ),
    )

    if es_postgres:
        op.execute(
            """
            UPDATE ingresos_inventario
            SET fuente_pago = CASE
                WHEN turno_caja_id IS NULL
                    THEN 'BALANCE'::fuente_pago_ingreso
                ELSE 'CAJA'::fuente_pago_ingreso
            END
            """
        )
    else:
        op.execute(
            """
            UPDATE ingresos_inventario
            SET fuente_pago = CASE
                WHEN turno_caja_id IS NULL THEN 'BALANCE'
                ELSE 'CAJA'
            END
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    op.drop_column("ingresos_inventario", "fuente_pago")

    if es_postgres:
        postgresql.ENUM(
            *_VALORES_FUENTE, name="fuente_pago_ingreso", create_type=False
        ).drop(bind, checkfirst=True)
