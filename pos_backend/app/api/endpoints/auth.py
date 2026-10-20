from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Usuario
from app.crud import crud_usuario
from app.core.security import create_access_token
from app.core.rate_limit import limite_login
from app.api.deps import get_current_active_user
from app.core.permisos import permisos_efectivos
from app.schemas.usuario import UsuarioResponse, UsuarioMe, PerfilUpdate, PasswordUpdate

router = APIRouter()


@router.post("/login", dependencies=[Depends(limite_login)])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = crud_usuario.authenticate(db, username=form_data.username, password=form_data.password)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not usuario.activo:
        # No se emite token para usuarios desactivados.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo. Contacta al administrador.",
        )
    token = create_access_token(subject=usuario.username, token_version=usuario.token_version or 0)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UsuarioMe)
def leer_usuario_actual(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return UsuarioMe(
        **UsuarioResponse.model_validate(current_user).model_dump(),
        permisos=permisos_efectivos(db, current_user.rol),
    )


@router.put("/me", response_model=UsuarioResponse)
def actualizar_perfil(
    datos: PerfilUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_usuario.actualizar_perfil(db, current_user, datos)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(
    datos: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    crud_usuario.cambiar_password(db, current_user, datos)
