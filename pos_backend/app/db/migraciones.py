"""Inicialización y migración del esquema con Alembic.

Reemplaza al antiguo `Base.metadata.create_all` + lista de `ALTER TABLE`
ad-hoc. Aplica `alembic upgrade head` reutilizando el motor/pool de la app.

Se ejecuta al arrancar la app (ver `app/main.py`) y en `scripts/crear_admin.py`.

Bases de datos "legadas" (creadas con `create_all` antes de adoptar Alembic) ya
tienen las tablas pero **no** la tabla `alembic_version`. Para no intentar
re-crearlas, se detectan y se marcan con `alembic stamp <revisión base>`
(`0000`), de modo que `upgrade head` solo aplica las migraciones posteriores
(`0001` en adelante) y repara las diferencias del esquema legado.

Tras migrar se **verifica** que el esquema real coincida con los modelos; si
no, se lanza un error con el detalle en lugar de arrancar con la base rota.
"""
from pathlib import Path
from typing import List, Tuple

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db import models  # noqa: F401  registra los modelos en Base.metadata
from app.db.base_class import Base
from app.db.session import engine


_RAIZ = Path(__file__).resolve().parent.parent.parent

# Tipos de diferencia que indican un esquema desalineado (no cosméticos).
_DIFERENCIAS_ESTRUCTURALES = frozenset(
    {
        "add_table",
        "remove_table",
        "add_column",
        "remove_column",
        "add_index",
        "remove_index",
        "add_fk",
        "remove_fk",
        "add_constraint",
        "remove_constraint",
    }
)


def _config() -> Config:
    config = Config(str(_RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(_RAIZ / "alembic"))
    return config


def _revision_base(config: Config) -> str:
    base = ScriptDirectory.from_config(config).get_base()
    if base is None:
        raise RuntimeError("No hay revisiones de Alembic en alembic/versions")
    return base


def _diferencias_estructurales(conexion) -> List[Tuple]:
    contexto = MigrationContext.configure(
        conexion,
        opts={"compare_type": False, "target_metadata": Base.metadata},
    )
    return [
        diff
        for diff in compare_metadata(contexto, Base.metadata)
        if diff[0] in _DIFERENCIAS_ESTRUCTURALES
    ]


def _verificar_esquema(conexion) -> None:
    """Comprueba que el esquema de la base coincide con los modelos."""
    problemas = _diferencias_estructurales(conexion)
    if problemas:
        detalle = "\n".join(f"  - {diff}" for diff in problemas)
        raise RuntimeError(
            "El esquema de la base de datos no coincide con los modelos tras "
            "aplicar las migraciones.\nRevisa las migraciones o el estado de la "
            f"base antes de arrancar:\n{detalle}"
        )


def inicializar_esquema() -> None:
    """Deja la base de datos al día aplicando todas las migraciones."""
    config = _config()

    tablas = set(inspect(engine).get_table_names())
    es_gestionada = "alembic_version" in tablas
    tiene_esquema = bool(tablas - {"alembic_version"})

    if tiene_esquema and not es_gestionada:
        # Base legada: marcar la revisión base sin volver a crear las tablas.
        with engine.begin() as conexion:
            config.attributes["connection"] = conexion
            try:
                command.stamp(config, _revision_base(config))
            finally:
                config.attributes.pop("connection", None)

    with engine.begin() as conexion:
        config.attributes["connection"] = conexion
        try:
            command.upgrade(config, "head")
            _verificar_esquema(conexion)
        finally:
            config.attributes.pop("connection", None)
