from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permiso
from app.crud import crud_proveedor
from app.db.models import Usuario
from app.db.session import get_db
from app.schemas.common import Pagina
from app.schemas.proveedor import (
    ProveedorCreate,
    ProveedorResponse,
    ProveedorUpdate,
)

router = APIRouter()


@router.post("/", response_model=ProveedorResponse)
def crear_proveedor(
    datos: ProveedorCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("proveedores.crear")),
):
    if datos.documento:
        existente = crud_proveedor.obtener_proveedor_por_documento(
            db, documento=datos.documento
        )
        if existente:
            raise HTTPException(
                status_code=400,
                detail="Ya existe un proveedor con este documento",
            )
    if crud_proveedor.obtener_proveedor_por_nombre(db, datos.nombre):
        raise HTTPException(
            status_code=400,
            detail="Ya existe un proveedor con ese nombre",
        )
    return crud_proveedor.crear_proveedor(db=db, datos=datos)


@router.get("/", response_model=Pagina[ProveedorResponse])
def leer_proveedores(
    skip: int = 0,
    limit: int = 50,
    buscar: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("proveedores.ver")),
):
    total, items = crud_proveedor.obtener_proveedores(
        db,
        skip=skip,
        limit=limit,
        buscar=buscar,
        orden=orden,
        direccion=direccion,
    )
    return Pagina(items=items, total=total, skip=skip, limit=limit)


@router.get("/{proveedor_id}", response_model=ProveedorResponse)
def leer_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("proveedores.ver")),
):
    proveedor = crud_proveedor.obtener_proveedor(db, proveedor_id=proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return proveedor


@router.put("/{proveedor_id}", response_model=ProveedorResponse)
def actualizar_proveedor(
    proveedor_id: int,
    datos: ProveedorUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("proveedores.editar")),
):
    if datos.documento:
        existente = crud_proveedor.obtener_proveedor_por_documento(
            db, documento=datos.documento
        )
        if existente and existente.id != proveedor_id:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro proveedor con este documento",
            )
    if datos.nombre:
        existente = crud_proveedor.obtener_proveedor_por_nombre(db, datos.nombre)
        if existente and existente.id != proveedor_id:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro proveedor con ese nombre",
            )
    return crud_proveedor.actualizar_proveedor(
        db=db, proveedor_id=proveedor_id, datos=datos
    )


@router.delete("/{proveedor_id}", status_code=204)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("proveedores.eliminar")),
):
    crud_proveedor.eliminar_proveedor(db=db, proveedor_id=proveedor_id)
    return None
