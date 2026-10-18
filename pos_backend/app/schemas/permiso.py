from typing import Dict, List

from pydantic import BaseModel


class PermisoItem(BaseModel):
    clave: str
    etiqueta: str


class ModuloPermisos(BaseModel):
    modulo: str
    permisos: List[PermisoItem]


class PermisosResponse(BaseModel):
    """Catálogo de permisos y el estado actual de cada rol configurable."""

    modulos: List[ModuloPermisos]
    # rol -> claves concedidas (Cajero y Mesero).
    roles: Dict[str, List[str]]
    todos: List[str]


class PermisosUpdate(BaseModel):
    permisos: List[str]


class PermisoRolResponse(BaseModel):
    rol: str
    permisos: List[str]
