from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import require_permiso
from app.schemas.caja import TurnoCajaCreate, TurnoCajaUpdate, TurnoCajaResponse, TurnoCajaHistorial, RegistroCajaCreate, RegistroCajaResponse, FacturaPendienteCierre, ResumenVentasTurno
from app.schemas.common import Pagina
from app.crud import crud_caja

router = APIRouter()

@router.post("/abrir", response_model=TurnoCajaResponse)
def abrir_caja(turno: TurnoCajaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.operar"))):
    return crud_caja.abrir_caja(db=db, turno=turno, usuario_id=current_user.id)

@router.put("/{turno_id}/cerrar", response_model=TurnoCajaResponse)
def cerrar_caja(turno_id: int, datos_cierre: TurnoCajaUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.operar"))):
    return crud_caja.cerrar_caja(db=db, turno_id=turno_id, datos_cierre=datos_cierre, usuario_id=current_user.id)

@router.get("/activa", response_model=TurnoCajaResponse)
def obtener_caja_activa(db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.ver"))):
    caja = crud_caja.obtener_caja_abierta(db)
    if not caja:
        raise HTTPException(status_code=404, detail="No hay ninguna caja abierta actualmente.")
    return caja

@router.get("/turnos", response_model=Pagina[TurnoCajaHistorial])
def listar_turnos(
    skip: int = 0,
    limit: int = 30,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    incluir_abierta: bool = False,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("caja.ver")),
):
    total, items = crud_caja.obtener_turnos(
        db=db,
        skip=skip,
        limit=limit,
        desde=desde,
        hasta=hasta,
        incluir_abierta=incluir_abierta,
        orden=orden,
        direccion=direccion,
    )
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.post("/movimientos", response_model=RegistroCajaResponse)
def registrar_movimiento(movimiento: RegistroCajaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.operar"))):
    caja_activa = crud_caja.obtener_caja_abierta(db)
    if not caja_activa:
        raise HTTPException(status_code=400, detail="Debe abrir la caja antes de registrar movimientos de dinero.")
    
    return crud_caja.registrar_movimiento(db=db, turno_id=caja_activa.id, movimiento=movimiento, usuario_id=current_user.id)

@router.get("/{turno_id}/movimientos", response_model=List[RegistroCajaResponse])
def obtener_movimientos_caja(turno_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.ver"))):
    return crud_caja.obtener_movimientos(db=db, turno_id=turno_id)


@router.get("/{turno_id}/pendientes", response_model=List[FacturaPendienteCierre])
def facturas_pendientes_cierre(turno_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("caja.ver"))):
    """Facturas del turno con saldo por cobrar (pasan a Crédito al cerrar)."""
    facturas = crud_caja.facturas_pendientes_cierre(db=db, turno_id=turno_id)
    return [
        FacturaPendienteCierre(
            id=f.id,
            cliente_id=f.cliente_id,
            cliente_nombre=f.cliente_nombre,
            nombre_eventual=f.nombre_eventual,
            total=f.total,
            saldo=f.saldo,
            es_eventual=(f.cliente.es_eventual if f.cliente else True),
        )
        for f in facturas
    ]


@router.get("/{turno_id}/resumen-ventas", response_model=ResumenVentasTurno)
def resumen_ventas_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("caja.ver")),
):
    """Ventas del turno, su parte a crédito y el total cobrado (para el cierre)."""
    return crud_caja.resumen_ventas_turno(db=db, turno_id=turno_id)
