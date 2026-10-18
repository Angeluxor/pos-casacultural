from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import require_permiso
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioResponse
from app.schemas.common import Pagina
from app.crud import crud_usuario

router = APIRouter()

@router.post("/", response_model=UsuarioResponse)
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    db_user = crud_usuario.get_usuario_by_username(db, username=usuario.username)
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado")
    return crud_usuario.crear_usuario(db=db, usuario=usuario)

@router.get("/", response_model=Pagina[UsuarioResponse])
def leer_usuarios(skip: int = 0, limit: int = 50, buscar: Optional[str] = None, orden: Optional[str] = None, direccion: Optional[str] = None, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    total, items = crud_usuario.obtener_usuarios(db, skip=skip, limit=limit, buscar=buscar, orden=orden, direccion=direccion)
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UsuarioResponse)
def leer_usuario(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    db_user = crud_usuario.get_usuario(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user

@router.put("/{user_id}", response_model=UsuarioResponse)
def actualizar_usuario(user_id: int, usuario: UsuarioUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    if usuario.activo is False and user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario")
    return crud_usuario.actualizar_usuario(db=db, user_id=user_id, usuario_in=usuario)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")
    crud_usuario.eliminar_usuario(db=db, user_id=user_id)
    return None
