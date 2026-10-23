"""Esquemas de los bolsillos de gastos vitales."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models import TipoMovimientoBolsillo


class BolsilloCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: Optional[str] = Field(default=None, max_length=300)
    # Saldo que ya existía en el bolsillo antes de usar la app. Se suma al
    # reservado, pero no se descuenta del efectivo/banco.
    saldo_inicial: float = Field(default=0, ge=0)


class BolsilloMovimientoCrear(BaseModel):
    tipo: TipoMovimientoBolsillo
    monto: float = Field(gt=0)
    nota: Optional[str] = Field(default=None, max_length=300)
    # Solo válido para aportes: registra un saldo inicial sin mover caja/banco.
    es_inicial: bool = False


class BolsilloBalance(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    reservado: float
    saldo_inicial: float = 0.0
    fecha_creacion: datetime


class BolsilloMovimientoResponse(BaseModel):
    id: int
    bolsillo_id: int
    fecha: datetime
    tipo: TipoMovimientoBolsillo
    monto: float
    nota: Optional[str] = None
    es_inicial: bool = False
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None

    class Config:
        from_attributes = True
