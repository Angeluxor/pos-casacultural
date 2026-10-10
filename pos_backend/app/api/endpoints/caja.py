from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import get_current_active_user
from app.schemas.caja import TurnoCajaCreate, TurnoCajaUpdate, TurnoCajaResponse, RegistroCajaCreate, RegistroCajaResponse
from app.crud import crud_caja

router = APIRouter()

@router.post("/abrir", response_model=TurnoCajaResponse)
def abrir_caja(turno: TurnoCajaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_caja.abrir_caja(db=db, turno=turno, usuario_id=current_user.id)

@router.put("/{turno_id}/cerrar", response_model=TurnoCajaResponse)
def cerrar_caja(turno_id: int, datos_cierre: TurnoCajaUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_caja.cerrar_caja(db=db, turno_id=turno_id, datos_cierre=datos_cierre, usuario_id=current_user.id)

@router.get("/activa", response_model=TurnoCajaResponse)
def obtener_caja_activa(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    caja = crud_caja.obtener_caja_abierta(db)
    if not caja:
        raise HTTPException(status_code=404, detail="No hay ninguna caja abierta actualmente.")
    return caja

@router.post("/movimientos", response_model=RegistroCajaResponse)
def registrar_movimiento(movimiento: RegistroCajaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    caja_activa = crud_caja.obtener_caja_abierta(db)
    if not caja_activa:
        raise HTTPException(status_code=400, detail="Debe abrir la caja antes de registrar movimientos de dinero.")
    
    return crud_caja.registrar_movimiento(db=db, turno_id=caja_activa.id, movimiento=movimiento, usuario_id=current_user.id)

@router.get("/{turno_id}/movimientos", response_model=List[RegistroCajaResponse])
def obtener_movimientos_caja(turno_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_caja.obtener_movimientos(db=db, turno_id=turno_id)
