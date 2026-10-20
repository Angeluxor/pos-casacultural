"""Esquemas de los bolsillos de gastos vitales."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models import TipoMovimientoBolsillo


class BolsilloCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: Optional[str] = Field(default=None, max_length=300)


class BolsilloMovimientoCrear(BaseModel):
    tipo: TipoMovimientoBolsillo
    monto: float = Field(gt=0)
    nota: Optional[str] = Field(default=None, max_length=300)


class BolsilloBalance(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    reservado: float
    fecha_creacion: datetime


class BolsilloMovimientoResponse(BaseModel):
    id: int
    bolsillo_id: int
    fecha: datetime
    tipo: TipoMovimientoBolsillo
    monto: float
    nota: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None

    class Config:
        from_attributes = True
