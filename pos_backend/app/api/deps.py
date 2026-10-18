from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.db.session import get_db
from app.db.models import Usuario
from app.crud import crud_usuario
from app.core.permisos import permisos_efectivos
from app.core.security import decode_access_token, TOKEN_TYPE

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username:
            raise credentials_exception
        # Solo se aceptan tokens de acceso (no refresh ni otros tipos).
        if payload.get("type") != TOKEN_TYPE:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    usuario = crud_usuario.get_usuario_by_username(db, username=str(username))
    if usuario is None:
        raise credentials_exception
    # Revocación: si la versión del token no coincide (p. ej. cambió la
    # contraseña), el token deja de ser válido aunque no haya expirado.
    if payload.get("ver", 0) != (usuario.token_version or 0):
        raise credentials_exception
    return usuario


def get_current_active_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if not current_user.activo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario inactivo")
    return current_user


def require_permiso(*claves: str):
    """Dependencia que exige al menos uno de los permisos indicados.

    Devuelve el usuario autenticado para que el endpoint lo siga usando como
    ``current_user``. El rol Admin siempre pasa (tiene todos los permisos).
    """

    def _dependencia(
        current_user: Usuario = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> Usuario:
        if not any(
            clave in permisos_efectivos(db, current_user.rol) for clave in claves
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        return current_user

    return _dependencia
