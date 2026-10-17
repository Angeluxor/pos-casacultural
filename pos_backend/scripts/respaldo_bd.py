r"""Respalda la base de datos (Neon o local) a un snapshot JSON portable.

No necesita `pg_dump` ni el cliente de Postgres: lee todas las tablas con
SQLAlchemy y las guarda en un único archivo JSON con metadatos (fecha, revisión
de Alembic y conteo de filas por tabla). El formato es estable y lo consume
`scripts/restaurar_bd.py`.

Uso desde `pos_backend/`:

    $env:PYTHONPATH = "."; .\venv\Scripts\python scripts\respaldo_bd.py
    # o con una cadena y un destino explícitos:
    python scripts\respaldo_bd.py --url "$env:DATABASE_URL_UNPOOLED" --salida respaldos\backup.json

Toma la cadena directa (sin pooling) si está definida: `DATABASE_URL_UNPOOLED`
y, si no, `DATABASE_URL` (lee `.env.local`/`.env`). Es una operación de solo
lectura, segura de correr contra producción.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import enum
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base_class import Base
from app.db import models  # noqa: F401  - registra las tablas en Base.metadata

RAIZ = Path(__file__).resolve().parent.parent
FORMATO = "pos-casiobsceno/respaldo/1"


def _codificar(column, valor):
    """Convierte un valor de la BD a algo serializable en JSON."""
    if valor is None:
        return None
    if isinstance(valor, enum.Enum):
        return valor.value
    if isinstance(valor, (dt.datetime, dt.date, dt.time)):
        return valor.isoformat()
    if isinstance(valor, decimal.Decimal):
        return str(valor)
    return valor


def _url_segura(url: str) -> str:
    """Devuelve la cadena sin la contraseña, para mostrarla."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:  # noqa: BLE001
        return "(url no interpretable)"


def _resolver_url(argumento: str | None) -> str:
    if argumento:
        return argumento
    load_dotenv(RAIZ / ".env.local")
    load_dotenv(RAIZ / ".env")
    return os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL") or ""


def _salida_por_defecto() -> Path:
    marca = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return RAIZ / "respaldos" / f"respaldo_{marca}.json"


def respaldar(url: str) -> dict:
    """Lee todas las tablas y devuelve el snapshot como diccionario."""
    engine = create_engine(url, pool_pre_ping=True)

    snapshot = {
        "formato": FORMATO,
        "generado_en": dt.datetime.now(dt.timezone.utc).isoformat(),
        "origen": _url_segura(url),
        "revision_alembic": None,
        "tablas": {},
        "conteos": {},
    }

    with engine.connect() as conexion:
        if inspect(conexion).has_table("alembic_version"):
            snapshot["revision_alembic"] = conexion.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()

        for tabla in Base.metadata.sorted_tables:
            columnas = [c.name for c in tabla.columns]
            filas = [
                [_codificar(tabla.columns[n], registro[n]) for n in columnas]
                for registro in conexion.execute(select(tabla)).mappings()
            ]
            snapshot["tablas"][tabla.name] = {"columnas": columnas, "filas": filas}
            snapshot["conteos"][tabla.name] = len(filas)

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo portable de la base de datos.")
    parser.add_argument("--url", help="Cadena de conexión (por defecto, la de .env.local).")
    parser.add_argument("--salida", help="Ruta del archivo JSON de salida.")
    parser.add_argument(
        "--compacto",
        action="store_true",
        help="Escribe el JSON sin sangría (archivo más pequeño).",
    )
    args = parser.parse_args()

    url = _resolver_url(args.url)
    if not url:
        print(
            "ERROR: no hay cadena de conexión. Define DATABASE_URL_UNPOOLED o "
            "DATABASE_URL, o pasa --url.",
            file=sys.stderr,
        )
        return 2

    salida = Path(args.salida) if args.salida else _salida_por_defecto()
    salida.parent.mkdir(parents=True, exist_ok=True)

    print(f"Respaldando {_url_segura(url)} …")
    snapshot = respaldar(url)

    salida.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=None if args.compacto else 2),
        encoding="utf-8",
    )

    print(f"Revisión Alembic: {snapshot['revision_alembic']}")
    for nombre, conteo in snapshot["conteos"].items():
        print(f"  - {nombre}: {conteo}")
    print(f"Total de filas: {sum(snapshot['conteos'].values())}")
    print(f"Respaldo escrito en: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
