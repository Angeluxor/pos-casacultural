from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
from app.db.models import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, PerfilUpdate, PasswordUpdate
from app.core.security import get_password_hash, verify_password

def get_usuario_by_username(db: Session, username: str):
    return db.query(Usuario).filter(Usuario.username == username).first()

def authenticate(db: Session, username: str, password: str):
    usuario = get_usuario_by_username(db, username=username)
    if not usuario:
        return None
    if not verify_password(password, usuario.hashed_password):
        return None
    return usuario

def get_usuario(db: Session, user_id: int):
    return db.query(Usuario).filter(Usuario.id == user_id).first()

def obtener_usuarios(db: Session, skip: int = 0, limit: int = 100, buscar: Optional[str] = None):
    query = db.query(Usuario)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(Usuario.username.ilike(filtro) | Usuario.nombre.ilike(filtro))
    total = query.count()
    items = query.order_by(Usuario.username).offset(skip).limit(limit).all()
    return total, items

def crear_usuario(db: Session, usuario: UsuarioCreate):
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
        usuario.hashed_password = get_password_hash(password)

    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar_perfil(db: Session, usuario: Usuario, datos_in: PerfilUpdate):
    if datos_in.nombre is not None:
        usuario.nombre = datos_in.nombre
    db.commit()
    db.refresh(usuario)
    return usuario


def cambiar_password(db: Session, usuario: Usuario, datos_in: PasswordUpdate):
    if not verify_password(datos_in.password_actual, usuario.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    if len(datos_in.password_nueva) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres")
    if verify_password(datos_in.password_nueva, usuario.hashed_password):
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente a la actual")

    usuario.hashed_password = get_password_hash(datos_in.password_nueva)
    db.commit()
    db.refresh(usuario)
    return usuario
