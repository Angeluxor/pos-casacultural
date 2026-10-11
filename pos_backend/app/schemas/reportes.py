from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class FilaVentaDetalle(BaseModel):
    id: int
    fecha: datetime
    cliente: Optional[str] = None
    vendedor: str
    estado: str
    total: float
    saldo: float


class VentaPorDia(BaseModel):
    fecha: datetime
    facturas: int
    anuladas: int
    total: float
    total_anulado: float


class FormaPagoMonto(BaseModel):
    forma_pago: str
    monto: float


class ReporteVentas(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    generado: datetime
    facturas: int
    facturas_anuladas: int
    total_vendido: float
    total_anulado: float
    neto: float
    por_dia: List[VentaPorDia]
    por_forma_pago: List[FormaPagoMonto]
    detalle: List[FilaVentaDetalle]


class FilaTopProducto(BaseModel):
    codigo: str
    nombre: str
    cantidad: int
    total: float
    precio_promedio: float


class ReporteTopProductos(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    generado: datetime
    renglones: int
    cantidad_total: int
    total_vendido: float
    items: List[FilaTopProducto]


class FilaCartera(BaseModel):
    cliente_id: int
    nombre: str
    documento: Optional[str] = None
    facturas: int
    total: float
    pagado: float
    saldo: float


class ReporteCartera(BaseModel):
    generado: datetime
    clientes_con_saldo: int
    total_cartera: float
    items: List[FilaCartera]


class FilaCierreCaja(BaseModel):
    id: int
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime] = None
    usuario_apertura: Optional[str] = None
    usuario_cierre: Optional[str] = None
    saldo_inicial: float
    entradas: float
    salidas: float
    esperado: float
    saldo_final_real: Optional[float] = None
    diferencia: Optional[float] = None


class ReporteCaja(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    generado: datetime
    turnos: int
    saldo_inicial_total: float
    entradas_total: float
    salidas_total: float
    esperado_total: float
    saldo_final_total: float
    diferencia_total: float
    por_forma_pago: List[FormaPagoMonto]
    items: List[FilaCierreCaja]


class FilaInventario(BaseModel):
    id: int
    codigo: str
    nombre: str
    precio: float
    stock: int
    valor: float


class ReporteInventario(BaseModel):
    generado: datetime
    productos: int
    unidades_totales: int
    valor_inventario: float
    items: List[FilaInventario]