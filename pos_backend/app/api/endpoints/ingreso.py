from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import FuentePagoIngreso, Usuario
from app.api.deps import require_permiso
from app.schemas.ingreso import (
    AnularIngreso,
    IngresoCreate,
    IngresoUpdate,
    IngresoResponse,
    PagarIngreso,
    ResolverIngreso,
)
from app.schemas.common import Pagina
from app.crud import crud_caja, crud_ingreso

router = APIRouter()


@router.post("/", response_model=IngresoResponse)
def crear_ingreso(
    datos: IngresoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.crear")),
):
    caja_activa = None
    if datos.fuente_pago == FuentePagoIngreso.CAJA:
        caja_activa = crud_caja.obtener_caja_abierta(db)
        if not caja_activa:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Debe abrir la caja antes de registrar un ingreso con fuente "
                    "«Caja activa», o elegir «Balance general»."
                ),
            )
    return crud_ingreso.crear_ingreso(
        db=db,
        turno_caja_id=caja_activa.id if caja_activa else None,
        datos=datos,
        usuario_id=current_user.id,
    )


@router.get("/", response_model=Pagina[IngresoResponse])
def listar_ingresos(
    skip: int = 0,
    limit: int = 20,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.ver")),
):
    total, items = crud_ingreso.obtener_ingresos(
        db=db, skip=skip, limit=limit, desde=desde, hasta=hasta, orden=orden, direccion=direccion
    )
    return Pagina(items=items, total=total, skip=skip, limit=limit)


@router.get("/{ingreso_id}", response_model=IngresoResponse)
def leer_ingreso(
    ingreso_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.ver")),
):
    return crud_ingreso.obtener_ingreso(db=db, ingreso_id=ingreso_id)


@router.put("/{ingreso_id}", response_model=IngresoResponse)
def editar_ingreso(
    ingreso_id: int,
    datos: IngresoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.editar")),
):
    return crud_ingreso.editar_ingreso(
        db=db, ingreso_id=ingreso_id, datos=datos, usuario_id=current_user.id
    )


@router.post("/{ingreso_id}/anular", response_model=IngresoResponse)
def anular_ingreso(
    ingreso_id: int,
    datos: AnularIngreso,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.anular")),
):
    """Anula un ingreso por error y revierte stock, caja y cuentas por pagar."""
    return crud_ingreso.anular_ingreso(
        db=db, ingreso_id=ingreso_id, motivo=datos.motivo, usuario_id=current_user.id
    )


@router.post("/{ingreso_id}/resolver", response_model=IngresoResponse)
def resolver_ingreso(
    ingreso_id: int,
    datos: ResolverIngreso,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.resolver")),
):
    return crud_ingreso.resolver_ingreso(
        db=db, ingreso_id=ingreso_id, justificacion=datos.justificacion
    )


@router.post("/{ingreso_id}/pagar", response_model=IngresoResponse)
def pagar_ingreso(
    ingreso_id: int,
    datos: PagarIngreso,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ingresos.pagar")),
):
    """Paga una compra a crédito y descuenta el total de la caja abierta."""
    return crud_ingreso.pagar_ingreso(
        db=db, ingreso_id=ingreso_id, datos=datos, usuario_id=current_user.id
    )