from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db.models import TurnoCaja, RegistroCaja, TipoMovimientoCaja
from app.schemas.caja import TurnoCajaCreate, TurnoCajaUpdate, RegistroCajaCreate
from app.core.timezone import get_colombia_time

def obtener_caja_abierta(db: Session):
    return db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()

def abrir_caja(db: Session, turno: TurnoCajaCreate, usuario_id: int):
    caja_abierta = obtener_caja_abierta(db)
    if caja_abierta:
        raise HTTPException(status_code=400, detail="Ya existe una caja abierta en este momento.")
    
    db_turno = TurnoCaja(
        usuario_apertura_id=usuario_id,
        saldo_inicial=turno.saldo_inicial,
        abierta=True
    )
    db.add(db_turno)
    db.commit()
    db.refresh(db_turno)
    
    # Registrar el saldo inicial como un movimiento de apertura (si es mayor a 0)
    if turno.saldo_inicial > 0:
        movimiento = RegistroCaja(
            turno_caja_id=db_turno.id,
            usuario_id=usuario_id,
            tipo=TipoMovimientoCaja.APERTURA,
            referencia="Apertura de caja",
            monto=turno.saldo_inicial,
            observacion="Saldo inicial reportado al abrir caja"
        )
        db.add(movimiento)
        db.commit()
        
    return db_turno

def cerrar_caja(db: Session, turno_id: int, datos_cierre: TurnoCajaUpdate, usuario_id: int):
    db_turno = db.query(TurnoCaja).filter(TurnoCaja.id == turno_id).first()
    if not db_turno or not db_turno.abierta:
        raise HTTPException(status_code=400, detail="El turno de caja no existe o ya está cerrado.")
        
    db_turno.saldo_final_real = datos_cierre.saldo_final_real
    db_turno.usuario_cierre_id = usuario_id
    db_turno.fecha_cierre = get_colombia_time()
    db_turno.abierta = False
    
    # Registrar el movimiento de cierre
    movimiento = RegistroCaja(
        turno_caja_id=db_turno.id,
        usuario_id=usuario_id,
        tipo=TipoMovimientoCaja.CIERRE,
        referencia="Cierre de caja",
        monto=datos_cierre.saldo_final_real,
        observacion="Saldo reportado al cajón al cerrar"
    )
    db.add(movimiento)
    db.commit()
    db.refresh(db_turno)
    return db_turno

def registrar_movimiento(db: Session, turno_id: int, movimiento: RegistroCajaCreate, usuario_id: int):
    db_movimiento = RegistroCaja(
        turno_caja_id=turno_id,
        usuario_id=usuario_id,
        tipo=movimiento.tipo,
        referencia=movimiento.referencia,
        forma_pago=movimiento.forma_pago,
        monto=movimiento.monto,
        observacion=movimiento.observacion
    )
    db.add(db_movimiento)
    db.commit()
    db.refresh(db_movimiento)
    return db_movimiento

def obtener_movimientos(db: Session, turno_id: int):
    return (
        db.query(RegistroCaja)
        .filter(RegistroCaja.turno_caja_id == turno_id)
        .order_by(RegistroCaja.fecha.asc(), RegistroCaja.id.asc())
        .all()
    )
