"""Esquemas del módulo de costos, recetas y costos manuales."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CostoManualCreate(BaseModel):
    producto_id: int
    fecha: Optional[date] = None
    costo_unitario: float = Field(ge=0)
    nota: Optional[str] = None


class CostoManualResponse(BaseModel):
    id: int
    producto_id: int
    producto_codigo: str
    producto_nombre: str
    fecha: datetime
    costo_unitario: float
    nota: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None


class RecetaItemInput(BaseModel):
    producto_id: int
    cantidad: float = Field(gt=0)


class RecetaUpsert(BaseModel):
    rendimiento: float = Field(gt=0)
    notas: Optional[str] = None
    items: List[RecetaItemInput] = Field(min_length=1)


class RecetaItemResponse(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    cantidad: float
    costo_unitario: Optional[float] = None
    subtotal: Optional[float] = None
    origen: Optional[str] = None


class RecetaResponse(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    precio: float
    rendimiento: float
    notas: Optional[str] = None
    costo_total: Optional[float] = None
    costo_unitario: Optional[float] = None
    completo: bool
    faltantes: List[str] = Field(default_factory=list)
    cmv_pct: Optional[float] = None
    margen: Optional[float] = None
    margen_pct: Optional[float] = None
    items: List[RecetaItemResponse] = Field(default_factory=list)


class ResumenCosto(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    precio: float
    stock: int
    misma_unidad_compra_venta: bool
    tiene_receta: bool
    mostrar_cmv: bool
    costo_vigente: Optional[float] = None
    origen_costo: Optional[str] = None
    costo_completo: bool
    faltantes: List[str] = Field(default_factory=list)
    mejor_precio_6s: Optional[float] = None
    mejor_proveedor: Optional[str] = None
    mejor_fecha: Optional[datetime] = None
    mejor_origen: Optional[str] = None
    variacion_6s: Optional[float] = None
    puntos_6s: int = 0
    cmv_pct: Optional[float] = None
    margen: Optional[float] = None
    margen_pct: Optional[float] = None


class HistorialCosto(BaseModel):
    fecha: datetime
    costo_unitario: float
    origen: str
    cantidad: Optional[float] = None
    proveedor: Optional[str] = None
    referencia: Optional[str] = None
    nota: Optional[str] = None


class InsumoOpcion(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    precio: float
    costo: Optional[float] = None
    origen: Optional[str] = None
    tiene_receta: bool
    completo: bool
    faltantes: List[str] = Field(default_factory=list)
