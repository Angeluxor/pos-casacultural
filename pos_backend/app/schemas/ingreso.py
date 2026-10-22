from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.db.models import (
    EstadoIngreso,
    FormaPago,
    FormaPagoIngreso,
    FuentePagoIngreso,
    TipoItemIngreso,
)


class IngresoItemBase(BaseModel):
    tipo: TipoItemIngreso
    producto_id: Optional[int] = None
    # Nombre para un "producto nuevo" o concepto del ítem "Otros".
    concepto: Optional[str] = None
    # Cantidad total en unidades. Si se compra por caja/paquete, el backend
    # la calcula como ``cantidad_formatos * unidades_por_formato``.
    cantidad: Optional[int] = None
    # Formato de compra (ej. 2 cajas de 12 unidades). Son opcionales: cuando
    # no se envían, la compra se interpreta por unidad.
    cantidad_formatos: Optional[int] = None
    unidades_por_formato: Optional[int] = None
    costo_formato: Optional[float] = None
    costo_unitario: Optional[float] = None
    valor: Optional[float] = None


class IngresoItemCreate(IngresoItemBase):
    # Solo para "producto nuevo": precio de venta con el que se creará.
    precio: Optional[float] = None


class IngresoItemUpdate(BaseModel):
    # Al editar solo se ajusta el costo de las líneas existentes. Se acepta el
    # costo unitario o, si la línea se compró por caja/paquete, el costo del
    # formato (el backend calcula el unitario automáticamente).
    id: int
    costo_unitario: Optional[float] = None
    costo_formato: Optional[float] = None


class IngresoItemResponse(BaseModel):
    id: int
    ingreso_id: int
    tipo: TipoItemIngreso
    producto_id: Optional[int]
    concepto: Optional[str]
    cantidad: Optional[int]
    cantidad_formatos: Optional[int] = None
    unidades_por_formato: Optional[int] = None
    costo_formato: Optional[float] = None
    costo_unitario: Optional[float]
    valor: Optional[float]

    class Config:
        from_attributes = True


class IngresoCreate(BaseModel):
    # Se puede enviar el id de un proveedor existente o, para crear uno nuevo
    # sobre la marcha, solo el nombre. El nombre también se acepta por
    # compatibilidad con los clientes anteriores de la API.
    proveedor_id: Optional[int] = None
    proveedor: Optional[str] = None
    # ``Caja activa`` exige turno abierto y puede generar salida de caja.
    # ``Balance general`` registra el ingreso sin tocar la caja.
    fuente_pago: FuentePagoIngreso = FuentePagoIngreso.CAJA
    forma_pago: FormaPagoIngreso
    total: float
    observacion: Optional[str] = None
    items: List[IngresoItemCreate] = []


class IngresoUpdate(BaseModel):
    proveedor_id: Optional[int] = None
    proveedor: Optional[str] = None
    # La cabecera se puede corregir después de registrar el ingreso. Al
    # cambiar la fuente o la forma de pago, el CRUD sincroniza el movimiento
    # de caja y el estado de pago.
    fuente_pago: Optional[FuentePagoIngreso] = None
    forma_pago: Optional[FormaPagoIngreso] = None
    observacion: Optional[str] = None
    items: List[IngresoItemUpdate] = []


class AnularIngreso(BaseModel):
    motivo: str


class ResolverIngreso(BaseModel):
    justificacion: str


class PagarIngreso(BaseModel):
    """Pago de una compra a crédito.

    Solo se permite efectivo o transferencia: son las formas que mueven uno de
    los dos bolsillos de la caja. El pago genera una salida por el total del
    ingreso y deja la cuenta por pagar en cero.
    """

    forma_pago: FormaPago


class IngresoResponse(BaseModel):
    id: int
    fecha: datetime
    usuario_id: int
    turno_caja_id: Optional[int]
    fuente_pago: FuentePagoIngreso
    proveedor_id: Optional[int] = None
    proveedor: Optional[str]
    forma_pago: FormaPagoIngreso
    total: float
    estado: EstadoIngreso
    justificacion: Optional[str]
    observacion: Optional[str]
    suma_items: float
    # Control de pago (compras a crédito).
    pagado: bool
    estado_pago: str
    fecha_pago: Optional[datetime] = None
    pagado_por_id: Optional[int] = None
    pagado_por_nombre: Optional[str] = None
    forma_pago_pago: Optional[FormaPago] = None
    # Anulación del ingreso (errores de registro). El registro se conserva
    # para auditoría, pero no cuenta en inventario, caja ni cuentas por pagar.
    anulada: bool = False
    motivo_anulacion: Optional[str] = None
    fecha_anulacion: Optional[datetime] = None
    anulada_por_id: Optional[int] = None
    anulada_por_nombre: Optional[str] = None
    items: List[IngresoItemResponse]

    class Config:
        from_attributes = True