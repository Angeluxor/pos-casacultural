"""Entorno de ejecución de Alembic para el POS Casi Obsceno.

Dos formas de uso:

* **CLI** (`alembic revision --autogenerate`, `alembic upgrade head`): Alembic
  crea el motor a partir de `DATABASE_URL_UNPOOLED`/`DATABASE_URL`.
* **Embebido** (arranque de la app): `app/db/migraciones.py` pasa una conexión ya
  abierta en `config.attributes["connection"]` para reutilizar el pool de la app.
"""
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Cargar variables desde pos_backend/.env.local y .env (igual que la app).
_RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(_RAIZ / ".env.local")
load_dotenv(_RAIZ / ".env")

# Los modelos deben importarse para que queden registrados en Base.metadata.
from app.db.base_class import Base  # noqa: E402
from app.db import models  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_URL_POR_DEFECTO = "postgresql://user:password@localhost/pos_casacultural"


def _url_migraciones() -> str:
    return (
        os.getenv("DATABASE_URL_UNPOOLED")
        or os.getenv("DATABASE_URL")
        or _URL_POR_DEFECTO
    )


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse a la base de datos."""
    context.configure(
        url=_url_migraciones(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones contra una conexión (compartida o nueva)."""
    conexion = config.attributes.get("connection")

    if conexion is not None:
        context.configure(
            connection=conexion,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    seccion = config.get_section(config.config_ini_section, {})
    seccion["sqlalchemy.url"] = _url_migraciones()
    motor = engine_from_config(seccion, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with motor.connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
