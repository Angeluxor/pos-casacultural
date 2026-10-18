from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import RolUsuario, Usuario
from app.api.deps import require_permiso
from app.core import permisos as core_permisos
from app.schemas.permiso import (
    ModuloPermisos,
    PermisoItem,
    PermisoRolResponse,
    PermisosResponse,
    PermisosUpdate,
)

router = APIRouter()


@router.get("/", response_model=PermisosResponse)
def obtener_permisos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("permisos.gestionar")),
):
    """Catálogo de permisos y lo que tiene hoy cada rol configurable."""
    modulos = [
        ModuloPermisos(
            modulo=nombre,
            permisos=[PermisoItem(clave=clave, etiqueta=etiqueta) for clave, etiqueta in claves],
        )
        for nombre, claves in core_permisos.CATALOGO
    ]
    roles = {
        rol.value: core_permisos.permisos_efectivos(db, rol)
        for rol in core_permisos.ROLES_CONFIGURABLES
    }
    return PermisosResponse(modulos=modulos, roles=roles, todos=core_permisos.TODOS)


@router.put("/{rol}", response_model=PermisoRolResponse)
def actualizar_permisos(
    rol: str,
    datos: PermisosUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("permisos.gestionar")),
):
    """Reemplaza los permisos de un rol configurable (Cajero o Mesero)."""
    try:
        rol_enum = RolUsuario(rol)
    except ValueError:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if rol_enum not in core_permisos.ROLES_CONFIGURABLES:
        raise HTTPException(
            status_code=400,
            detail="El rol Admin siempre tiene todos los permisos y no se puede editar.",
        )
    claves = core_permisos.guardar_permisos(db, rol_enum, datos.permisos)
    return PermisoRolResponse(rol=rol_enum.value, permisos=claves)
