from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.db.models import FormaPago, TipoMovimientoCaja

class TurnoCajaBase(BaseModel):
    saldo_inicial_efectivo: float = 0.0
    saldo_inicial_banco: float = 0.0

class TurnoCajaCreate(TurnoCajaBase):
    usuario_apertura_id: Optional[int] = None

class TurnoCajaUpdate(BaseModel):
    saldo_final_real_efectivo: float
    saldo_final_real_banco: float
    usuario_cierre_id: Optional[int] = None

class TurnoCajaResponse(BaseModel):
    id: int
    usuario_apertura_id: int
    usuario_cierre_id: Optional[int]
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime]
    saldo_inicial_efectivo: float
    saldo_inicial_banco: float
    saldo_final_real_efectivo: Optional[float]
    saldo_final_real_banco: Optional[float]
    abierta: bool

    class Config:
        from_attributes = True

class TurnoCajaHistorial(TurnoCajaResponse):
    usuario_apertura_nombre: Optional[str] = None
    usuario_cierre_nombre: Optional[str] = None
    entradas_efectivo: float = 0.0
    entradas_banco: float = 0.0
    salidas_efectivo: float = 0.0
    salidas_banco: float = 0.0
    esperado_efectivo: float = 0.0
    esperado_banco: float = 0.0
    diferencia_efectivo: Optional[float] = None
    diferencia_banco: Optional[float] = None

    class Config:
        from_attributes = True

class RegistroCajaBase(BaseModel):
    tipo: TipoMovimientoCaja
    referencia: str
    forma_pago: FormaPago
    monto: float
    observacion: Optional[str] = None

class RegistroCajaCreate(RegistroCajaBase):
    usuario_id: Optional[int] = None
    # No pedimos turno_caja_id porque el endpoint lo deduce de la caja que esté abierta actualmente.
    # Tampoco exigimos usuario_id: se toma del token autenticado.

class RegistroCajaResponse(RegistroCajaBase):
    id: int
    turno_caja_id: int
    usuario_id: int
    fecha: datetime

    class Config:
        from_attributes = True
