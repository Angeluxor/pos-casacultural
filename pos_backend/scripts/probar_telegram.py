"""Envía un mensaje de prueba al chat de Telegram configurado.

Uso:
    python scripts/probar_telegram.py "Hola, esta es una prueba"
"""
import sys
from pathlib import Path

# Permite `python scripts/probar_telegram.py` sin depender de PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.notificaciones import enviar_mensaje_telegram, telegram_configurado


def main() -> int:
    if not telegram_configurado():
        print(
            "Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID. "
            "Configúralos en el entorno antes de probar."
        )
        return 1

    texto = " ".join(sys.argv[1:]).strip() or (
        "✅ Prueba de avisos del POS: Telegram está configurado."
    )
    if enviar_mensaje_telegram(texto):
        print("Mensaje enviado correctamente.")
        return 0
    print("No se pudo enviar el mensaje. Revisa el token, el chat ID y la red.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
