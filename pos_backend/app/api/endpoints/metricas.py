from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_permiso
from app.core import metricas as nucleo
from app.db.models import Usuario
from app.db.session import get_db
from app.schemas.metricas import LoteMuestrasCliente, ResumenMetricas
from app.services import metricas as servicio

router = APIRouter()


@router.get("/resumen", response_model=ResumenMetricas)
def resumen_metricas(
    horas: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("metricas.ver")),
):
    """Rendimiento de la API: percentiles por ruta, lentas y diagnóstico."""
    # Lo que aún está en el búfer también cuenta.
    nucleo.volcar()
    return servicio.resumen(db, horas=horas)


@router.post("/cliente", status_code=204)
def recibir_muestras_cliente(
    lote: LoteMuestrasCliente,
    current_user: Usuario = Depends(get_current_active_user),
):
    """Recibe los tiempos que midió el navegador (cualquier usuario con sesión)."""
    nucleo.registrar_muestras_cliente([m.model_dump() for m in lote.muestras])
