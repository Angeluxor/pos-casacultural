from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.db.models import EstadoFactura, FormaPago

class DetalleFacturaCreate(BaseModel):
    producto_id: int
    cantidad: int

class DetalleFacturaResponse(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario: float
    subtotal: float
    anulado: bool = False

    class Config:
        from_attributes = True

class FacturaCreate(BaseModel):
    cliente_id: Optional[int] = None
    vendedor_id: Optional[int] = None
    detalles: List[DetalleFacturaCreate]

class FacturaAnular(BaseModel):
    motivo: Optional[str] = None

class ItemFacturaCreate(BaseModel):
    producto_id: int
    cantidad: int

class ItemFacturaUpdate(BaseModel):
    cantidad: int

class PagoCreate(BaseModel):
    cajero_id: Optional[int] = None
    valor: float
    forma_pago: FormaPago

class PagoResponse(BaseModel):
    id: int
    fecha: datetime
    valor: float
    forma_pago: FormaPago
    cajero_id: int

    class Config:
        from_attributes = True

class FacturaResponse(BaseModel):
    id: int
    cliente_id: Optional[int]
    vendedor_id: int
    fecha: datetime
    total: float
    saldo: float
    estado: EstadoFactura
    motivo_anulacion: Optional[str] = None
    fecha_anulacion: Optional[datetime] = None
    anulada_por_id: Optional[int] = None
    detalles: List[DetalleFacturaResponse] = []
    pagos: List[PagoResponse] = []

    class Config:
        from_attributes = True
