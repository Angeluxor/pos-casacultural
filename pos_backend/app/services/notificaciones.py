"""Avisos al equipo cuando entra un ticket de feedback.

La integración es opcional: si ``TELEGRAM_BOT_TOKEN`` o ``TELEGRAM_CHAT_ID``
no están configurados, no se envía nada y el feedback se guarda normalmente.
El envío se hace en segundo plano para no retrasar la respuesta al usuario.
"""
import json
import logging
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import FRONTEND_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

MAX_COMENTARIO_TELEGRAM = 900


def telegram_configurado() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def _ruta_del_contexto(contexto: Optional[dict]) -> str:
    if isinstance(contexto, dict):
        ruta = contexto.get("ruta")
        if isinstance(ruta, str) and ruta.strip():
            return ruta.strip()
    return "—"


def construir_mensaje_feedback(
    *,
    feedback_id: int,
    tipo: str,
    prioridad: str,
    usuario_nombre: str,
    comentario: str,
    contexto: Optional[dict] = None,
) -> str:
    """Arma un mensaje de texto plano, seguro para Telegram."""
    texto = (comentario or "").strip()
    if len(texto) > MAX_COMENTARIO_TELEGRAM:
        texto = texto[: MAX_COMENTARIO_TELEGRAM - 1].rstrip() + "…"
    return "\n".join(
        [
            f"🎫 Nuevo ticket #{feedback_id}",
            f"Tipo: {tipo} · Prioridad: {prioridad}",
            f"De: {usuario_nombre}",
            f"Ruta: {_ruta_del_contexto(contexto)}",
            "",
            texto,
            "",
            f"Ver bandeja: {FRONTEND_URL}/feedback",
        ]
    )


def enviar_mensaje_telegram(
    texto: str,
    *,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 10.0,
) -> bool:
    """Envía un mensaje por la Bot API. Devuelve ``False`` si no se pudo."""
    token = (token or TELEGRAM_BOT_TOKEN).strip()
    chat_id = (chat_id or TELEGRAM_CHAT_ID).strip()
    if not token or not chat_id:
        return False

    datos = urlencode(
        {
            "chat_id": chat_id,
            "text": texto,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    peticion = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=datos,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(peticion, timeout=timeout) as respuesta:
            contenido = json.loads(respuesta.read().decode("utf-8"))
    except Exception:
        # No se registra la URL porque contiene el token del bot.
        logger.warning("No se pudo enviar el aviso de Telegram", exc_info=True)
        return False

    if not contenido.get("ok"):
        logger.warning(
            "Telegram rechazó el aviso: %s", contenido.get("description")
        )
        return False
    return True


def notificar_feedback_telegram(
    *,
    feedback_id: int,
    tipo: str,
    prioridad: str,
    usuario_nombre: str,
    comentario: str,
    contexto: Optional[dict] = None,
) -> bool:
    if not telegram_configurado():
        return False
    return enviar_mensaje_telegram(
        construir_mensaje_feedback(
            feedback_id=feedback_id,
            tipo=tipo,
            prioridad=prioridad,
            usuario_nombre=usuario_nombre,
            comentario=comentario,
            contexto=contexto,
        )
    )
