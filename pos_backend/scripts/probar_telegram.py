"""Envía un mensaje de prueba al chat de Telegram configurado.

Uso:
    python scripts/probar_telegram.py "Hola, esta es una prueba"

Toma la configuración de la base de datos (tabla ``configuracion``) o, si no
existe, de las variables TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.
"""
import sys
from pathlib import Path

# Permite `python scripts/probar_telegram.py` sin depender de PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.db.session import SessionLocal
from app.services.configuracion import configuracion_telegram
from app.services.notificaciones import enviar_mensaje_telegram


def main() -> int:
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    db = SessionLocal()
    try:
        token_db, chat_db = configuracion_telegram(db)
        token = token_db or token
        chat_id = chat_db or chat_id
    except Exception:
        # La tabla puede no existir todavía en una base sin migrar.
        pass
    finally:
        db.close()

    if not token or not chat_id:
        print(
            "Faltan el token y/o el chat ID de Telegram. "
            "Configúralos en la app, en la base o en el entorno."
        )
        return 1

    texto = " ".join(sys.argv[1:]).strip() or (
        "✅ Prueba de avisos del POS: Telegram está configurado."
    )
    if enviar_mensaje_telegram(texto, token=token, chat_id=chat_id):
        print("Mensaje enviado correctamente.")
        return 0
    print("No se pudo enviar el mensaje. Revisa el token, el chat ID y la red.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
