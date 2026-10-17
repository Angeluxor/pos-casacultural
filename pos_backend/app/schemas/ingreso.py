from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.db.models import FormaPagoIngreso, EstadoIngreso, TipoItemIngreso


class IngresoItemBase(BaseModel):
    tipo: TipoItemIngreso
    producto_id: Optional[int] = None
    # Nombre para un "producto nuevo" o concepto del ítem "Otros".
    concepto: Optional[str] = None
    cantidad: Optional[int] = None
    costo_unitario: Optional[float] = None
    valor: Optional[float] = None


class IngresoItemCreate(IngresoItemBase):
    # Solo para "producto nuevo": precio de venta con el que se creará.
    precio: Optional[float] = None


class IngresoItemUpdate(BaseModel):
    # Al editar solo se ajusta el costo unitario de las líneas existentes.
    id: int
    costo_unitario: Optional[float] = None


class IngresoItemResponse(BaseModel):
    id: int
    ingreso_id: int
    tipo: TipoItemIngreso
    producto_id: Optional[int]
    concepto: Optional[str]
    cantidad: Optional[int]
    costo_unitario: Optional[float]
    valor: Optional[float]

    class Config:
        from_attributes = True


class IngresoCreate(BaseModel):
    proveedor: Optional[str] = None
    forma_pago: FormaPagoIngreso
    total: float
    observacion: Optional[str] = None
    items: List[IngresoItemCreate] = []


class IngresoUpdate(BaseModel):
    proveedor: Optional[str] = None
    observacion: Optional[str] = None
    items: List[IngresoItemUpdate] = []


class ResolverIngreso(BaseModel):
    justificacion: str


class IngresoResponse(BaseModel):
    id: int
    fecha: datetime
    usuario_id: int
    turno_caja_id: Optional[int]
    proveedor: Optional[str]
    forma_pago: FormaPagoIngreso
    total: float
    estado: EstadoIngreso
    justificacion: Optional[str]
    observacion: Optional[str]
    suma_items: float
    items: List[IngresoItemResponse]

    class Config:
        from_attributes = True