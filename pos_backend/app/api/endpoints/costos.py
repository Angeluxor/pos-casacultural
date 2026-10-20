"""Endpoints del módulo de costos, recetas y costos manuales."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_permiso
from app.db.models import Producto, Usuario
from app.db.session import get_db
from app.schemas.costos import (
    CostoManualCreate,
    CostoManualResponse,
    HistorialCosto,
    InsumoOpcion,
    RecetaResponse,
    RecetaUpsert,
    ResumenCosto,
)
from app.services import costos as costos_service

router = APIRouter()


@router.get("/resumen", response_model=List[ResumenCosto])
def resumen_costos(
    buscar: Optional[str] = None,
    solo_1a1: bool = False,
    solo_con_costo: bool = False,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    filas = costos_service.resumen_costos(db, buscar=buscar)
    if solo_1a1:
        filas = [fila for fila in filas if fila["mostrar_cmv"]]
    if solo_con_costo:
        filas = [fila for fila in filas if fila["costo_vigente"] is not None]
    return filas


@router.get(
    "/productos/{producto_id}/historial",
    response_model=List[HistorialCosto],
)
def historial_producto(
    producto_id: int,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    existe = (
        db.query(Producto.id).filter(Producto.id == producto_id).first()
    )
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return costos_service.historial_producto(
        db, producto_id=producto_id, desde=desde, hasta=hasta
    )


@router.get("/insumos", response_model=List[InsumoOpcion])
def insumos_receta(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    return costos_service.insumos_receta(db)


@router.get("/recetas", response_model=List[RecetaResponse])
def listar_recetas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    return costos_service.listar_recetas(db)


@router.get("/recetas/{producto_id}", response_model=RecetaResponse)
def obtener_receta(
    producto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    return costos_service.obtener_receta(db, producto_id)


@router.put("/recetas/{producto_id}", response_model=RecetaResponse)
def guardar_receta(
    producto_id: int,
    datos: RecetaUpsert,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.editar")),
):
    return costos_service.guardar_receta(db, producto_id, datos)


@router.delete("/recetas/{producto_id}", status_code=204)
def eliminar_receta(
    producto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.editar")),
):
    costos_service.eliminar_receta(db, producto_id)


@router.get("/manuales", response_model=List[CostoManualResponse])
def listar_costos_manuales(
    producto_id: Optional[int] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.ver")),
):
    return costos_service.listar_costos_manuales(
        db, producto_id=producto_id, limit=limit
    )


@router.post("/manuales", response_model=CostoManualResponse)
def crear_costo_manual(
    datos: CostoManualCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.editar")),
):
    return costos_service.crear_costo_manual(
        db, datos, usuario_id=current_user.id
    )


@router.delete("/manuales/{costo_id}", status_code=204)
def eliminar_costo_manual(
    costo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("costos.editar")),
):
    costos_service.eliminar_costo_manual(db, costo_id)
