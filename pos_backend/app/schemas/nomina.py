from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FilaDeudaNomina(BaseModel):
    """Una factura a crédito del cliente vinculado a un usuario."""

    factura_id: int
    fecha: datetime
    total: float
    saldo: float


class DeudaNominaResponse(BaseModel):
    usuario_id: int
    cliente_id: int
    cliente_nombre: str
    saldo_total: float
    facturas: List[FilaDeudaNomina] = []


class DescuentoNominaCreate(BaseModel):
    # Si no se indica monto, se aplica toda la deuda pendiente.
    monto: Optional[float] = None
    # Nota libre para la auditoría: período de nómina, autorización, etc.
    nota: Optional[str] = None


class FilaDescuentoNomina(BaseModel):
    """Evento de auditoría de un descuento de nómina."""

    id: int
    fecha: datetime
    usuario_id: Optional[int] = None
    usuario_nombre: str
    cliente_id: Optional[int] = None
    cliente_nombre: str
    monto: float
    saldo_pendiente: float
    facturas_afectadas: int
    registrado_por: str
    nota: Optional[str] = None


class FacturaAfectadaNomina(BaseModel):
    """Factura concreta que cubrió un evento de descuento de nómina."""

    factura_id: int
    fecha: datetime
    total: float
    abono: float
    saldo_actual: float


class FilaHistorialNomina(FilaDescuentoNomina):
    facturas: List[FacturaAfectadaNomina] = []


class DescuentoNominaResponse(BaseModel):
    descuento_id: int
    usuario_id: int
    cliente_id: int
    cliente_nombre: str
    monto_aplicado: float
    saldo_pendiente: float
    facturas_afectadas: int
    nota: Optional[str] = None


class HistorialNominaResponse(BaseModel):
    usuario_id: int
    usuario_nombre: str
    cliente_id: Optional[int] = None
    cliente_nombre: Optional[str] = None
    saldo_total: float
    descuentos: int
    monto_total: float
    items: List[FilaHistorialNomina] = []
