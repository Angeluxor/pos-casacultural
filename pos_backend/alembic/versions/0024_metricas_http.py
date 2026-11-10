"""métricas de rendimiento por petición

Agrega ``metricas_http`` para diagnosticar la lentitud con datos: tiempo total,
tiempo en base de datos, consultas, conexiones nuevas, inactividad previa y
mediciones del navegador. Se purgan solas a los 30 días.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metricas_http",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origen", sa.String(length=10), nullable=False),
        sa.Column("metodo", sa.String(length=8), nullable=False),
        sa.Column("ruta", sa.String(length=160), nullable=False),
        sa.Column("estado", sa.Integer(), nullable=False),
        sa.Column("ms_total", sa.Float(), nullable=False),
        sa.Column("ms_db", sa.Float(), nullable=False),
        sa.Column("consultas", sa.Integer(), nullable=False),
        sa.Column("conexiones_nuevas", sa.Integer(), nullable=False),
        sa.Column("inactivo_s", sa.Float(), nullable=True),
        sa.Column("primera_tras_arranque", sa.Boolean(), nullable=False),
        sa.Column("conexion", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metricas_http_creado_en", "metricas_http", ["creado_en"])
    op.create_index("ix_metricas_http_ruta", "metricas_http", ["ruta"])


def downgrade() -> None:
    op.drop_index("ix_metricas_http_ruta", table_name="metricas_http")
    op.drop_index("ix_metricas_http_creado_en", table_name="metricas_http")
    op.drop_table("metricas_http")
