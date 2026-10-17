"""Ordenamiento de listados paginados por listas blancas de columnas.

El frontend envía la clave pública de la columna (por ejemplo ``"precio"``) y la
dirección (``"asc"`` o ``"desc"``). Aquí se traduce a un ``ORDER BY`` de
SQLAlchemy validándola contra un mapa conocido, de modo que un valor arbitrario
nunca llega al SQL (sin riesgo de inyección).
"""
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy.orm import Query

DIRECCIONES_VALIDAS = ("asc", "desc")


def ordenar(
    query: Query,
    orden: Optional[str],
    direccion: Optional[str],
    columnas: Mapping[str, Any],
    por_defecto: Sequence[Any],
    desempate: Optional[Any] = None,
) -> Query:
    """Aplica ``ORDER BY`` a ``query``.

    - ``columnas``: mapa {clave pública: columna o expresión SQLAlchemy}. Solo se
      aceptan claves de este mapa (lista blanca).
    - ``por_defecto``: criterios usados cuando no se pide un orden válido.
    - ``desempate``: criterio secundario que hace estable la paginación (para que
      ordenar por una columna con valores repetidos no repita ni omita filas
      entre páginas).
    """
    if orden and orden in columnas:
        columna = columnas[orden]
        criterio = columna.desc() if direccion == "desc" else columna.asc()
        criterios = [criterio]
        if desempate is not None:
            criterios.append(desempate)
        return query.order_by(*criterios)
    return query.order_by(*por_defecto)
