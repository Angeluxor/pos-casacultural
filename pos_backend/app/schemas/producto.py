from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.db.models import TipoMovimientoInventario, MotivoAjuste

class ProductoBase(BaseModel):
    codigo: str
    nombre: str
    precio: float
    # Si la compra y la venta usan la misma unidad. Se usa en Costos para
    # decidir si tiene sentido mostrar la relación CMV/precio de venta.
    misma_unidad_compra_venta: bool = True

class ProductoCreate(ProductoBase):
    stock_inicial: int = 0
    usuario_id: Optional[int] = None  # Quien crea el producto (se toma del token autenticado)

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    precio: Optional[float] = None
    misma_unidad_compra_venta: Optional[bool] = None

class ProductoResponse(ProductoBase):
    id: int
    stock: int

    class Config:
        from_attributes = True

class KardexBase(BaseModel):
    tipo_movimiento: TipoMovimientoInventario
    cantidad: int
    referencia: Optional[str] = None
    # Solo se usan en los ajustes manuales de stock.
    motivo: Optional[MotivoAjuste] = None
    motivo_detalle: Optional[str] = None

class KardexCreate(KardexBase):
    usuario_id: Optional[int] = None

class KardexResponse(KardexBase):
    id: int
    producto_id: int
    usuario_id: int
    fecha: datetime
    saldo_stock: int

    class Config:
        from_attributes = True
