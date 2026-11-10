from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MuestraCliente(BaseModel):
    """Una petición medida desde el navegador (incluye red y espera real)."""

    metodo: str = Field(max_length=8)
    ruta: str = Field(max_length=200)
    # 0 = sin respuesta (timeout o red caída).
    estado: int = Field(ge=0, le=599)
    ms: float = Field(ge=0, le=600_000)
    conexion: Optional[str] = Field(default=None, max_length=16)


class LoteMuestrasCliente(BaseModel):
    muestras: List[MuestraCliente] = Field(max_length=50)


class ProcesoInfo(BaseModel):
    proceso_desde: datetime
    arranque_ms: Optional[float] = None
    en_bufer: int
    descartadas: int


class ResumenServidor(BaseModel):
    n: int
    p50: float
    p95: float
    max: float
    pct_lentas: float
    pct_db: float
    arranques_en_frio: int
    tras_inactividad: int
    conexiones_nuevas: int
    errores_5xx: int


class ResumenCliente(BaseModel):
    n: int
    p50: float
    p95: float
    max: float
    fallidas: int


class RutaMetrica(BaseModel):
    ruta: str
    n: int
    p50: float
    p95: float
    max: float
    db_prom: float
    pct_db: float
    consultas_prom: float
    errores_5xx: int
    cliente_p95: Optional[float] = None


class PuntoHora(BaseModel):
    hora: str
    n: int
    p50: float
    p95: float


class PeticionLenta(BaseModel):
    creado_en: datetime
    metodo: str
    ruta: str
    estado: int
    ms_total: float
    ms_db: float
    consultas: int
    conexiones_nuevas: int
    inactivo_s: Optional[float] = None
    primera_tras_arranque: bool


class ResumenMetricas(BaseModel):
    horas: int
    generado: datetime
    proceso: ProcesoInfo
    servidor: ResumenServidor
    cliente: ResumenCliente
    diagnostico: List[str]
    rutas: List[RutaMetrica]
    por_hora: List[PuntoHora]
    lentas: List[PeticionLenta]
