from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from fastapi import HTTPException
from typing import Optional
from app.db.models import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, PerfilUpdate, PasswordUpdate
from app.core.security import get_password_hash, verify_password
from app.core.config import PASSWORD_MIN_LENGTH
from app.core.orden import ordenar


def _validar_password(password: str) -> None:
    if len(password or "") < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres",
        )

def get_usuario_by_username(db: Session, username: str):
    if not username:
        return None
    usuario = db.query(Usuario).filter(Usuario.username == username).first()
    if usuario is None:
        usuario = (
            db.query(Usuario)
            .filter(func.lower(Usuario.username) == username.strip().lower())
            .first()
        )
    return usuario

def authenticate(db: Session, username: str, password: str):
    usuario = get_usuario_by_username(db, username=username)
    if not usuario:
        return None
    if not verify_password(password, usuario.hashed_password):
        return None
    return usuario

def get_usuario(db: Session, user_id: int):
    return db.query(Usuario).filter(Usuario.id == user_id).first()

def obtener_usuarios(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    buscar: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
):
    query = db.query(Usuario)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(Usuario.username.ilike(filtro) | Usuario.nombre.ilike(filtro))
    total = query.count()
    items = (
        ordenar(
            query,
            orden,
            direccion,
            {
                "username": Usuario.username,
                "nombre": Usuario.nombre,
                "rol": Usuario.rol,
                "activo": Usuario.activo,
            },
            [Usuario.username.asc(), Usuario.id.asc()],
            desempate=Usuario.id.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items

def crear_usuario(db: Session, usuario: UsuarioCreate):
    _validar_password(usuario.password)
    hashed_password = get_password_hash(usuario.password)
    db_usuario = Usuario(
        username=usuario.username,
        nombre=usuario.nombre,
        hashed_password=hashed_password,
        rol=usuario.rol,
        activo=usuario.activo
    )
    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)
    return db_usuario


def actualizar_usuario(db: Session, user_id: int, usuario_in: UsuarioUpdate):
    usuario = get_usuario(db, user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    datos = usuario_in.model_dump(exclude_unset=True)
    password = datos.pop("password", None)

    for campo, valor in datos.items():
        setattr(usuario, campo, valor)

    if password:
        _validar_password(password)
        usuario.hashed_password = get_password_hash(password)
        # Invalida los tokens vigentes del usuario al cambiar la contraseña.
        usuario.token_version = (usuario.token_version or 0) + 1

    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar_perfil(db: Session, usuario: Usuario, datos_in: PerfilUpdate):
    if datos_in.nombre is not None:
        usuario.nombre = datos_in.nombre
    db.commit()
    db.refresh(usuario)
    return usuario


def eliminar_usuario(db: Session, user_id: int):
    usuario = get_usuario(db, user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        db.delete(usuario)
        db.commit()
    except IntegrityError:
        # El usuario tiene registros asociados (ventas, caja, inventario): no se
        # puede borrar sin romper el historial. Se sugiere desactivarlo.
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: el usuario tiene movimientos registrados "
                "(ventas, caja o inventario). Desactívalo en su lugar."
            ),
        )


def cambiar_password(db: Session, usuario: Usuario, datos_in: PasswordUpdate):
    if not verify_password(datos_in.password_actual, usuario.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    _validar_password(datos_in.password_nueva)
    if verify_password(datos_in.password_nueva, usuario.hashed_password):
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente a la actual")

    usuario.hashed_password = get_password_hash(datos_in.password_nueva)
    # Invalida los tokens vigentes (incluido el de la sesión actual).
    usuario.token_version = (usuario.token_version or 0) + 1
    db.commit()
    db.refresh(usuario)
    return usuario
