"""categorías de caja y bolsillos de gastos vitales

Agrega:

- ``caja.categoria``: clasificación operativa de los movimientos manuales
  (Aporte cultural, Arriendo, etc.). Los movimientos históricos de apertura y
  cierre se clasifican; las entradas/salidas históricas quedan en NULL porque no
  se puede distinguir con seguridad si fueron manuales o automáticas.
- ``bolsillos``: fondos virtuales para apartar dinero de la liquidez diaria.
- ``bolsillo_movimientos``: aportes y retiros que forman el saldo del bolsillo.

Los bolsillos no mueven la caja: solo separan una parte del saldo disponible.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQLAlchemy guarda los nombres de los miembros del Enum, no sus valores.
# El modelo TipoMovimientoBolsillo tiene APORTE="Aporte" y RETIRO="Retiro";
# por eso el tipo de PostgreSQL se crea con etiquetas en mayúscula.
_VALORES_TIPO_BOLSILLO = ("APORTE", "RETIRO")


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"
    tipo_bolsillo = (
        postgresql.ENUM(
            *_VALORES_TIPO_BOLSILLO,
            name="tipomovimientobolsillo",
            create_type=False,
        )
        if es_postgres
        else sa.String()
    )
    if es_postgres:
        tipo_bolsillo.create(bind, checkfirst=True)

    with op.batch_alter_table("caja") as batch:
        batch.add_column(sa.Column("categoria", sa.String(), nullable=True))
    op.create_index("ix_caja_categoria", "caja", ["categoria"], unique=False)

    # Los movimientos de apertura/cierre son siempre automáticos y se pueden
    # clasificar sin ambigüedad. Las entradas/salidas históricas se dejan en
    # NULL: la UI las muestra como «Sin categoría» para no adivinar.
    op.execute(
        "UPDATE caja SET categoria = 'Apertura' "
        "WHERE categoria IS NULL AND tipo = 'APERTURA'"
    )
    op.execute(
        "UPDATE caja SET categoria = 'Cierre' "
        "WHERE categoria IS NULL AND tipo = 'CIERRE'"
    )

    op.create_table(
        "bolsillos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_por_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["creado_por_id"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bolsillos_id"), "bolsillos", ["id"], unique=False)
    op.create_index(
        op.f("ix_bolsillos_nombre"), "bolsillos", ["nombre"], unique=False
    )
    op.create_index(
        op.f("ix_bolsillos_activo"), "bolsillos", ["activo"], unique=False
    )

    op.create_table(
        "bolsillo_movimientos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bolsillo_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", tipo_bolsillo, nullable=False),
        sa.Column("monto", sa.Float(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bolsillo_id"], ["bolsillos.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bolsillo_movimientos_id"),
        "bolsillo_movimientos",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_bolsillo_movimientos_bolsillo_fecha",
        "bolsillo_movimientos",
        ["bolsillo_id", "fecha"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(
        "ix_bolsillo_movimientos_bolsillo_fecha",
        table_name="bolsillo_movimientos",
    )
    op.drop_index(
        op.f("ix_bolsillo_movimientos_id"), table_name="bolsillo_movimientos"
    )
    op.drop_table("bolsillo_movimientos")

    op.drop_index(op.f("ix_bolsillos_activo"), table_name="bolsillos")
    op.drop_index(op.f("ix_bolsillos_nombre"), table_name="bolsillos")
    op.drop_index(op.f("ix_bolsillos_id"), table_name="bolsillos")
    op.drop_table("bolsillos")

    op.drop_index("ix_caja_categoria", table_name="caja")
    with op.batch_alter_table("caja") as batch:
        batch.drop_column("categoria")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            *_VALORES_TIPO_BOLSILLO,
            name="tipomovimientobolsillo",
            create_type=False,
        ).drop(bind, checkfirst=True)
