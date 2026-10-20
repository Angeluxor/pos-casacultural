import base64
import binascii
import json
import os
import re
from datetime import timedelta
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, defer, joinedload

from app.core.timezone import get_colombia_time
from app.db.models import Feedback, Usuario
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate

MAX_CAPTURA_BYTES = 2 * 1024 * 1024
MAX_CONTEXTO_CARACTERES = 20_000
MAX_FEEDBACK_POR_MINUTO = 5


def _firma_valida(mime: str, contenido: bytes) -> bool:
    if mime == "image/png":
        return contenido.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return contenido.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return (
            len(contenido) >= 12
            and contenido[:4] == b"RIFF"
            and contenido[8:12] == b"WEBP"
        )
    return False


def _decodificar_captura(
    datos: FeedbackCreate,
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    if not datos.captura_base64:
        return None, None, None
    if not datos.captura_mime:
        raise HTTPException(
            status_code=400, detail="La captura no tiene un tipo de imagen válido."
        )

    valor = datos.captura_base64.strip()
    if valor.startswith("data:"):
        _, _, valor = valor.partition(",")
    if len(valor) > 3_000_000:
        raise HTTPException(
            status_code=400,
            detail="La captura es demasiado grande (máximo 2 MB).",
        )

    try:
        contenido = base64.b64decode(valor, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=400, detail="La captura no es una imagen válida."
        )

    if not contenido:
        raise HTTPException(status_code=400, detail="La captura está vacía.")
    if len(contenido) > MAX_CAPTURA_BYTES:
        raise HTTPException(
            status_code=400,
            detail="La captura es demasiado grande (máximo 2 MB).",
        )
    if not _firma_valida(datos.captura_mime, contenido):
        raise HTTPException(
            status_code=400,
            detail="El contenido de la captura no coincide con el tipo de imagen.",
        )

    nombre = os.path.basename((datos.captura_nombre or "captura").strip())
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)[:120] or "captura"
    return contenido, datos.captura_mime, nombre


def _validar_contexto(contexto: dict) -> dict:
    try:
        texto = json.dumps(contexto, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail="El contexto técnico no es un JSON válido."
        )
    if len(texto) > MAX_CONTEXTO_CARACTERES:
        raise HTTPException(
            status_code=400, detail="El contexto técnico es demasiado grande."
        )
    return contexto


def _serializar_etiquetas(etiquetas: Optional[list[str]]) -> Optional[str]:
    if not etiquetas:
        return None
    return ", ".join(etiquetas)


def contar_feedback_reciente(db: Session, usuario_id: int) -> int:
    """Cuenta los envíos del usuario en el último minuto.

    Es un límite sencillo contra doble clic o spam accidental. El middleware
    global de rate limit sigue protegiendo el resto de la API.
    """
    desde = get_colombia_time() - timedelta(minutes=1)
    return (
        db.query(Feedback.id)
        .filter(Feedback.usuario_id == usuario_id, Feedback.creado_en >= desde)
        .count()
    )


def crear_feedback(db: Session, datos: FeedbackCreate, usuario: Usuario) -> Feedback:
    contenido, mime, nombre = _decodificar_captura(datos)
    feedback = Feedback(
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre or usuario.username or "Usuario",
        tipo=datos.tipo,
        comentario=datos.comentario,
        contexto=_validar_contexto(datos.contexto),
        estado="Nuevo",
        prioridad="Media",
        tiene_captura=contenido is not None,
        captura=contenido,
        captura_mime=mime,
        captura_nombre=nombre,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def obtener_feedback(db: Session, feedback_id: int) -> Optional[Feedback]:
    return db.query(Feedback).filter(Feedback.id == feedback_id).first()


def listar_feedback(
    db: Session,
    skip: int = 0,
    limit: int = 25,
    buscar: Optional[str] = None,
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
    prioridad: Optional[str] = None,
):
    query = db.query(Feedback)
    if estado:
        query = query.filter(Feedback.estado == estado)
    if tipo:
        query = query.filter(Feedback.tipo == tipo)
    if prioridad:
        query = query.filter(Feedback.prioridad == prioridad)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(
            or_(
                Feedback.comentario.ilike(filtro),
                Feedback.usuario_nombre.ilike(filtro),
                Feedback.etiquetas.ilike(filtro),
            )
        )
    total = query.count()
    items = (
        query.options(
            joinedload(Feedback.responsable), defer(Feedback.captura)
        )
        .order_by(Feedback.creado_en.desc(), Feedback.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items


def obtener_captura(
    db: Session, feedback_id: int
) -> Tuple[bytes, str, str]:
    feedback = obtener_feedback(db, feedback_id)
    if not feedback or not feedback.captura:
        raise HTTPException(status_code=404, detail="Captura no encontrada")
    return (
        feedback.captura,
        feedback.captura_mime or "application/octet-stream",
        feedback.captura_nombre or "captura",
    )


def actualizar_feedback(
    db: Session, feedback_id: int, datos: FeedbackUpdate
) -> Feedback:
    feedback = obtener_feedback(db, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")

    campos = datos.model_dump(exclude_unset=True)

    if "estado" in campos:
        estado = campos["estado"]
        if estado is None:
            raise HTTPException(status_code=400, detail="El estado no puede ser nulo.")
        feedback.estado = estado
        if estado in ("Resuelto", "Descartado"):
            if feedback.resuelto_en is None:
                feedback.resuelto_en = get_colombia_time()
        else:
            feedback.resuelto_en = None

    if "prioridad" in campos:
        prioridad = campos["prioridad"]
        if prioridad is None:
            raise HTTPException(
                status_code=400, detail="La prioridad no puede ser nula."
            )
        feedback.prioridad = prioridad

    if "etiquetas" in campos:
        feedback.etiquetas = _serializar_etiquetas(campos["etiquetas"])

    if "notas_internas" in campos:
        feedback.notas_internas = campos["notas_internas"] or None

    if "responsable_id" in campos:
        responsable_id = campos["responsable_id"]
        if responsable_id is not None:
            responsable = (
                db.query(Usuario)
                .filter(Usuario.id == responsable_id, Usuario.activo.is_(True))
                .first()
            )
            if not responsable:
                raise HTTPException(
                    status_code=400,
                    detail="El responsable indicado no existe o está inactivo.",
                )
        feedback.responsable_id = responsable_id

    feedback.actualizado_en = get_colombia_time()
    db.commit()
    db.refresh(feedback)
    return feedback
