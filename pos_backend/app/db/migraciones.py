"""Migraciones ligeras e idempotentes para bases de datos ya existentes.

`Base.metadata.create_all` crea tablas que faltan pero **no** agrega columnas a
tablas existentes. Mientras no adoptemos Alembic, este módulo aplica los cambios
aditivos necesarios en cada arranque (PostgreSQL soporta `ADD COLUMN IF NOT
EXISTS`, así que es seguro repetirlo).

Cuando migremos a Alembic, este paso se reemplaza por `alembic upgrade head`.
"""
from sqlalchemy import text

from app.db.session import engine

_MIGRACIONES = [
    # Clientes: celular y correo (documento queda opcional, ya existía).
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS celular VARCHAR",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS correo VARCHAR",
    # Detalle de factura: marca de línea retirada (persistencia para traza).
    "ALTER TABLE detalles_factura ADD COLUMN IF NOT EXISTS anulado BOOLEAN NOT NULL DEFAULT false",
    # Factura: traza de anulación.
    "ALTER TABLE facturas ADD COLUMN IF NOT EXISTS motivo_anulacion VARCHAR",
    "ALTER TABLE facturas ADD COLUMN IF NOT EXISTS fecha_anulacion TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE facturas ADD COLUMN IF NOT EXISTS anulada_por_id INTEGER",
]


def aplicar_migraciones() -> None:
    with engine.begin() as conn:
        for sql in _MIGRACIONES:
            conn.execute(text(sql))
