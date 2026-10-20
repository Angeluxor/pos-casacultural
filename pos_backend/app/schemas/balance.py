"""Esquemas del balance general operativo.

El balance es una foto del negocio al momento de la consulta. El estado de
resultados sí se filtra por el período indicado (ventas, costo y gastos). El
patrimonio se calcula como residual (activos menos pasivos), porque el sistema
no lleva aportes de capital ni retiros.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.bolsillos import BolsilloBalance


class SaldosCaja(BaseModel):
    efectivo: float
    banco: float
    reservado: float = 0.0
    disponible: float = 0.0
    abierta: bool
    turno_id: Optional[int] = None
    origen: str


class FilaInventarioBalance(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    stock: int
    costo_unitario: float
    valor: float
    origen: str


class CuentaPorPagar(BaseModel):
    ingreso_id: int
    fecha: datetime
    proveedor: Optional[str] = None
    total: float
    estado_ingreso: str
    forma_pago_pago: Optional[str] = None
    fecha_pago: Optional[datetime] = None


class BalanceActivos(BaseModel):
    efectivo: float
    banco: float
    # Parte de efectivo + banco que está apartada en bolsillos. No se suma dos
    # veces al total de activos: el dinero sigue existiendo, solo no está
    # disponible para la operación diaria.
    reservado: float
    disponible: float
    inventario: float
    cartera: float
    total: float


class BalancePasivos(BaseModel):
    cuentas_por_pagar: float
    total: float


class BalancePatrimonio(BaseModel):
    total: float


class ResultadosPeriodo(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    ventas_netas: float
    costo_ventas: float
    utilidad_bruta: float
    gastos: float
    gastos_caja: float
    gastos_otros: float
    utilidad: float
    margen: float
    facturas: int
    productos_vendidos_sin_costo: int


class BalanceGeneral(BaseModel):
    generado: datetime
    fecha_corte: datetime
    caja: SaldosCaja
    activos: BalanceActivos
    pasivos: BalancePasivos
    patrimonio: BalancePatrimonio
    resultados: ResultadosPeriodo
    inventario: List[FilaInventarioBalance]
    cuentas_por_pagar: List[CuentaPorPagar]
    bolsillos: List[BolsilloBalance]
    total_reservado: float
    productos_sin_costo: int
    valor_inventario_precio_venta: float
    compras_credito_pendientes: int
