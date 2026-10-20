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

class ItemFacturaCreate(BaseModel):
    producto_id: int
    cantidad: int


class ItemFacturaUpdate(BaseModel):
    cantidad: int


class FacturaCreate(BaseModel):
    cliente_id: Optional[int] = None
    # Nombre temporal/eventual cuando el cliente no se registra.
    nombre_eventual: Optional[str] = None
    detalles: List[ItemFacturaCreate] = []


class FacturaClienteUpdate(BaseModel):
    cliente_id: int


class FacturaAnular(BaseModel):
    motivo: Optional[str] = None


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
    cliente_nombre: Optional[str] = None
    nombre_eventual: Optional[str] = None
    vendedor_id: int
    turno_caja_id: Optional[int] = None
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


class TotalesFacturas(BaseModel):
    """Totales de todas las facturas que cumplen los filtros de la lista."""

    total_facturado: float
    saldo: float
    total_anulado: float
    neto: float
    facturas_anuladas: int


class PaginaFacturas(BaseModel):
    items: List[FacturaResponse]
    total: int
    skip: int
    limit: int
    totales: TotalesFacturas
