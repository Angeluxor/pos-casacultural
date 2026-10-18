from pydantic import BaseModel
from typing import List, Optional
from app.db.models import RolUsuario

class UsuarioBase(BaseModel):
    username: str
    nombre: str
    rol: RolUsuario = RolUsuario.CAJERO
    activo: bool = True

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[RolUsuario] = None
    activo: Optional[bool] = None

class PerfilUpdate(BaseModel):
    nombre: Optional[str] = None

class PasswordUpdate(BaseModel):
    password_actual: str
    password_nueva: str

class UsuarioResponse(UsuarioBase):
    id: int

    class Config:
        from_attributes = True


class UsuarioMe(UsuarioResponse):
    """Usuario de la sesión, con sus permisos efectivos (para la UI)."""

    permisos: List[str] = []
