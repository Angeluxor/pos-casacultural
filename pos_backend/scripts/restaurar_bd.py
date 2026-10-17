r"""Restaura un respaldo generado por `scripts/respaldo_bd.py` en una base de datos.

El respaldo es un JSON con las filas de todas las tablas (formato
`pos-casiobsceno/respaldo/1`). Este script las vuelve a insertar respetando el
orden de las claves foráneas y, en PostgreSQL, reajusta las secuencias de los
`id` para que los siguientes inserts no choquen.

Seguridad:
  * Por defecto es un **simulacro** (dry-run): muestra qué haría y no escribe.
  * Para escribir de verdad hay que pasar `--confirmar`.
  * Si la base destino ya tiene datos, se niega salvo que se añada `--force`
    (que borra primero las filas existentes).

Uso desde `pos_backend/`:

    # Simulacro (recomendado antes de tocar nada):
    python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json

    # Restauración real en una base vacía:
    python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json --confirmar

    # Restauración sobre una base con datos (los reemplaza):
    python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json --confirmar --force

Usa la cadena `DATABASE_URL_UNPOOLED`/`DATABASE_URL` de `.env.local`, o `--url`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy import Date, DateTime
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base_class import Base
from app.db import models  # noqa: F401  - registra las tablas en Base.metadata

RAIZ = Path(__file__).resolve().parent.parent
FORMATO = "pos-casiobsceno/respaldo/1"


def _url_segura(url: str) -> str:
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


def _a_enum(enum_class, valor):
    if valor is None or isinstance(valor, enum_class):
        return valor
    try:
        return enum_class(valor)
    except ValueError:
        try:
            return enum_class[valor]
        except KeyError:
            return valor


def _decodificar(column, valor):
    """Reconstruye el valor Python a partir del JSON, según el tipo de columna."""
    if valor is None:
        return None
    enum_class = getattr(column.type, "enum_class", None)
    if enum_class is not None:
        return _a_enum(enum_class, valor)
    if isinstance(column.type, DateTime) and isinstance(valor, str):
        return dt.datetime.fromisoformat(valor)
    if isinstance(column.type, Date) and isinstance(valor, str):
        return dt.date.fromisoformat(valor)
    return valor


def _filas_decodificadas(tabla, datos) -> list[dict]:
    columnas = datos["columnas"]
    return [
        {n: _decodificar(tabla.columns[n], v) for n, v in zip(columnas, fila)}
        for fila in datos["filas"]
    ]


def _reiniciar_secuencias(conexion, tablas) -> None:
    """En PostgreSQL, deja cada secuencia de `id` por encima del máximo insertado."""
    if conexion.dialect.name != "postgresql":
        return
    for tabla in tablas:
        id_col = tabla.columns.get("id")
        if id_col is None or not id_col.primary_key:
            continue
        secuencia = conexion.execute(
            text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": tabla.name}
        ).scalar()
        if not secuencia:
            continue
        conexion.execute(
            text(
                f"SELECT setval('{secuencia}', "
                f"COALESCE((SELECT MAX(id) FROM {tabla.name}), 1), "
                f"(SELECT COUNT(*) > 0 FROM {tabla.name}))"
            )
        )


def _ejecutar(snapshot: dict, url: str, args) -> int:
    if snapshot.get("formato") != FORMATO:
        print(
            f"ERROR: formato de respaldo desconocido: {snapshot.get('formato')}",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(url, pool_pre_ping=True)

    if args.crear_esquema:
        Base.metadata.create_all(engine)

    tablas = [t for t in Base.metadata.sorted_tables if t.name in snapshot["tablas"]]
    nombres_en_destino = set(inspect(engine).get_table_names())

    faltantes = [t.name for t in tablas if t.name not in nombres_en_destino]
    if faltantes:
        print(
            "ERROR: faltan tablas en el destino: "
            + ", ".join(faltantes)
            + ". Aplica las migraciones (alembic upgrade head) o usa --crear-esquema.",
            file=sys.stderr,
        )
        return 2

    with engine.connect() as conexion:
        totales = {
            t.name: conexion.execute(select(func.count()).select_from(t)).scalar()
            for t in tablas
        }

    con_datos = {n: c for n, c in totales.items() if c}
    print(f"Origen del respaldo: {snapshot.get('origen')}")
    print(f"Revisión Alembic   : {snapshot.get('revision_alembic')}")
    print(f"Destino            : {_url_segura(url)}")
    for nombre in snapshot["conteos"]:
        print(f"  {nombre:<18} respaldo={snapshot['conteos'][nombre]:<6} destino={totales.get(nombre, 0)}")

    if con_datos and not args.force:
        print(
            "\nEl destino ya tiene datos. Usa --force para reemplazarlos o "
            "restaura en una base vacía.",
            file=sys.stderr,
        )
        return 3

    if not args.confirmar:
        print("\nSimulacro: no se escribió nada. Añade --confirmar para restaurar.")
        return 0

    with engine.begin() as conexion:
        if con_datos:
            for tabla in reversed(tablas):
                conexion.execute(tabla.delete())
        for tabla in tablas:
            filas = _filas_decodificadas(tabla, snapshot["tablas"][tabla.name])
            if filas:
                conexion.execute(tabla.insert(), filas)
        _reiniciar_secuencias(conexion, tablas)

    print(f"\nRestauración completa: {sum(snapshot['conteos'].values())} filas.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restaura un respaldo portable de la base de datos."
    )
    parser.add_argument("--archivo", required=True, help="Ruta del JSON de respaldo.")
    parser.add_argument("--url", help="Cadena de conexión destino (por defecto, .env.local).")
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Escribe de verdad (sin esto es un simulacro).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permite restaurar sobre una base con datos (los reemplaza).",
    )
    parser.add_argument(
        "--crear-esquema",
        action="store_true",
        help="Crea las tablas con create_all si no existen (base nueva).",
    )
    args = parser.parse_args()

    archivo = Path(args.archivo)
    if not archivo.is_file():
        print(f"ERROR: no existe el archivo {archivo}", file=sys.stderr)
        return 2

    url = _resolver_url(args.url)
    if not url:
        print(
            "ERROR: no hay cadena de conexión. Define DATABASE_URL_UNPOOLED o "
            "DATABASE_URL, o pasa --url.",
            file=sys.stderr,
        )
        return 2

    snapshot = json.loads(archivo.read_text(encoding="utf-8"))
    return _ejecutar(snapshot, url, args)


if __name__ == "__main__":
    raise SystemExit(main())
