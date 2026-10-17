import jwt
import uuid

from datetime import datetime, timedelta, timezone

import bcrypt

from app.core.config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    BCRYPT_ROUNDS,
)

TOKEN_TYPE = "access"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("utf-8")


def create_access_token(
    subject: str,
    token_version: int = 0,
    expires_minutes: int | None = None,
) -> str:
    """Crea un JWT de acceso con claims de trazabilidad y revocación.

    - `jti`: identificador único del token (para auditoría / listas negras futuras).
    - `iat`: momento de emisión.
    - `type`: tipo de token (permite añadir refresh tokens a futuro sin ambigüedad).
    - `ver`: versión de token del usuario; si cambia (p. ej. al cambiar la
      contraseña) los tokens emitidos antes quedan invalidados.
    """
    minutos = expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
        "jti": str(uuid.uuid4()),
        "type": TOKEN_TYPE,
        "ver": token_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
