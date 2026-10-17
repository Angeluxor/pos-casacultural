from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import get_current_active_user, require_admin
from app.schemas.ingreso import IngresoCreate, IngresoUpdate, IngresoResponse, ResolverIngreso
from app.schemas.common import Pagina
from app.crud import crud_caja, crud_ingreso

router = APIRouter()


@router.post("/", response_model=IngresoResponse)
def crear_ingreso(
    datos: IngresoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    caja_activa = crud_caja.obtener_caja_abierta(db)
    if not caja_activa:
        raise HTTPException(status_code=400, detail="Debe abrir la caja antes de registrar un ingreso.")
    return crud_ingreso.crear_ingreso(
        db=db, turno_caja_id=caja_activa.id, datos=datos, usuario_id=current_user.id
    )


@router.get("/", response_model=Pagina[IngresoResponse])
def listar_ingresos(
    skip: int = 0,
    limit: int = 20,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    total, items = crud_ingreso.obtener_ingresos(
        db=db, skip=skip, limit=limit, desde=desde, hasta=hasta
    )
    return Pagina(items=items, total=total, skip=skip, limit=limit)


@router.get("/{ingreso_id}", response_model=IngresoResponse)
def leer_ingreso(
    ingreso_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_ingreso.obtener_ingreso(db=db, ingreso_id=ingreso_id)


@router.put("/{ingreso_id}", response_model=IngresoResponse)
def editar_ingreso(
    ingreso_id: int,
    datos: IngresoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_ingreso.editar_ingreso(db=db, ingreso_id=ingreso_id, datos=datos)


@router.post("/{ingreso_id}/resolver", response_model=IngresoResponse)
def resolver_ingreso(
    ingreso_id: int,
    datos: ResolverIngreso,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin),
):
    return crud_ingreso.resolver_ingreso(
        db=db, ingreso_id=ingreso_id, justificacion=datos.justificacion
    )