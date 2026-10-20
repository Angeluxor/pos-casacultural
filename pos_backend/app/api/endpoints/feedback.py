from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permiso
from app.crud import crud_feedback
from app.db.models import Usuario
from app.db.session import get_db
from app.schemas.common import Pagina
from app.schemas.feedback import (
    EstadoFeedback,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackUpdate,
    PrioridadFeedback,
    TipoFeedback,
)

router = APIRouter()


@router.post("/", response_model=FeedbackResponse)
def crear_feedback(
    datos: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("feedback.crear")),
):
    if (
        crud_feedback.contar_feedback_reciente(db, current_user.id)
        >= crud_feedback.MAX_FEEDBACK_POR_MINUTO
    ):
        raise HTTPException(
            status_code=429,
            detail="Enviaste varios comentarios seguidos. Espera un minuto antes de reintentar.",
        )
    return crud_feedback.crear_feedback(db=db, datos=datos, usuario=current_user)


@router.get("/", response_model=Pagina[FeedbackResponse])
def leer_feedback(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    buscar: Optional[str] = None,
    estado: Optional[EstadoFeedback] = None,
    tipo: Optional[TipoFeedback] = None,
    prioridad: Optional[PrioridadFeedback] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("feedback.gestionar")),
):
    total, items = crud_feedback.listar_feedback(
        db,
        skip=skip,
        limit=limit,
        buscar=buscar,
        estado=estado,
        tipo=tipo,
        prioridad=prioridad,
    )
    return Pagina(items=items, total=total, skip=skip, limit=limit)


@router.get("/{feedback_id}/captura")
def leer_captura(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("feedback.gestionar")),
):
    contenido, mime, nombre = crud_feedback.obtener_captura(db, feedback_id)
    return Response(
        content=contenido,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{nombre}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{feedback_id}", response_model=FeedbackResponse)
def actualizar_feedback(
    feedback_id: int,
    datos: FeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("feedback.gestionar")),
):
    return crud_feedback.actualizar_feedback(db, feedback_id, datos)
