import os
import secrets
import warnings

from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

# Entorno de ejecución: "development" (por defecto) o "production".
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

_DEFAULT_SECRET = "dev-secret-change-me"
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Rondas de bcrypt. 12 es el valor recomendado actual; subirlo encarece el
# hashing (mejor resistencia a fuerza bruta) a costa de CPU en cada login.
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

# Longitud mínima exigida para las contraseñas (nuevas y cambios).
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))

# Rate limiting en memoria. El login es lo más sensible; además hay un tope
# global por IP para frenar abuso genérico.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "10"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "60"))
GLOBAL_MAX_REQUESTS = int(os.getenv("GLOBAL_MAX_REQUESTS", "600"))
GLOBAL_WINDOW_SECONDS = int(os.getenv("GLOBAL_WINDOW_SECONDS", "60"))

# Cabeceras de seguridad. `HSTS` solo tiene efecto sobre HTTPS, por eso en local
# (development) se omite para no "romper" http://localhost.
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "true" if IS_PRODUCTION else "false").strip().lower() in {"1", "true", "yes", "si", "sí"}

CORS_ORIGINS = [
    origen.strip()
    for origen in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origen.strip()
]


def validar_configuracion() -> None:
    """Comprueba ajustes peligrosos y avisa (o falla) según el entorno.

    Se llama al arrancar la aplicación y desde las pruebas.
    """
    if IS_PRODUCTION and SECRET_KEY == _DEFAULT_SECRET:
        raise RuntimeError(
            "SECRET_KEY no configurada: define una clave aleatoria en producción "
            "(por ejemplo: python -c \"import secrets; print(secrets.token_urlsafe(64))\")."
        )
    if not IS_PRODUCTION and SECRET_KEY == _DEFAULT_SECRET:
        warnings.warn(
            "Usando SECRET_KEY de desarrollo. No la uses en producción.",
            stacklevel=2,
        )
    if len(SECRET_KEY) < 32 and IS_PRODUCTION:
        warnings.warn(
            "SECRET_KEY de producción corta (<32 caracteres); usa una más larga.",
            stacklevel=2,
        )


def generar_secret_key() -> str:
    """Utilidad para generar una SECRET_KEY segura."""
    return secrets.token_urlsafe(64)
