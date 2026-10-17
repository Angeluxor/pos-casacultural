from pydantic import BaseModel
from typing import Dict, List, Optional


class DashboardKpis(BaseModel):
    ventas_hoy_total: float
    ventas_hoy_cantidad: int
    ventas_7d_total: float
    cartera_total: float
    facturas_pendientes: int


class VentaDia(BaseModel):
    fecha: str
    total: float
    cantidad: int


class ProductoBajoStock(BaseModel):
    id: int
    codigo: str
    nombre: str
    stock: int


class CajaResumen(BaseModel):
    abierta: bool
    turno_id: Optional[int] = None
    saldo_inicial_efectivo: float = 0.0
    saldo_inicial_banco: float = 0.0
    entradas_efectivo: float = 0.0
    entradas_banco: float = 0.0
    salidas_efectivo: float = 0.0
    salidas_banco: float = 0.0
    esperado_efectivo: float = 0.0
    esperado_banco: float = 0.0


class DashboardResumen(BaseModel):
    kpis: DashboardKpis
    ventas_ultimos_7_dias: List[VentaDia]
    productos_bajo_stock: List[ProductoBajoStock]
    facturas_por_estado: Dict[str, int]
    caja: CajaResumen
    total_clientes: int
    total_productos: int
