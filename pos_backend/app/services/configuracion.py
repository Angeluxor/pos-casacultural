"""Lectura y escritura de ajustes internos en la base de datos."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Configuracion

CLAVE_TELEGRAM_TOKEN = "telegram_bot_token"
CLAVE_TELEGRAM_CHAT_ID = "telegram_chat_id"


def obtener_valor(db: Session, clave: str) -> Optional[str]:
    fila = db.get(Configuracion, clave)
    if not fila or not fila.valor:
        return None
    return fila.valor.strip() or None


def guardar_valor(db: Session, clave: str, valor: Optional[str]) -> Configuracion:
    fila = db.get(Configuracion, clave)
    if fila is None:
        fila = Configuracion(clave=clave)
    fila.valor = (valor or "").strip() or None
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


def configuracion_telegram(
    db: Session,
) -> tuple[Optional[str], Optional[str]]:
    """Token y chat ID guardados en la base; ``None`` si no hay configurar."""
    return (
        obtener_valor(db, CLAVE_TELEGRAM_TOKEN),
        obtener_valor(db, CLAVE_TELEGRAM_CHAT_ID),
    )
