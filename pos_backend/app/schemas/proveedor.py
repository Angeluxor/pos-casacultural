import re
from typing import Optional

from pydantic import BaseModel, field_validator


CELULAR_RE = re.compile(r"\d{7,15}")
CORREO_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class ProveedorValidado(BaseModel):
    @field_validator("nombre", check_fields=False)
    @classmethod
    def validar_nombre(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El nombre del proveedor es obligatorio.")
        return v

    @field_validator("documento", check_fields=False)
    @classmethod
    def limpiar_documento(cls, v):
        if v is None:
            return v
        return v.strip() or None

    @field_validator("celular", check_fields=False)
    @classmethod
    def validar_celular(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not CELULAR_RE.fullmatch(v):
            raise ValueError("El celular debe contener solo números (7 a 15 dígitos).")
        return v

    @field_validator("correo", check_fields=False)
    @classmethod
    def validar_correo(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not CORREO_RE.fullmatch(v):
            raise ValueError("El correo no tiene un formato válido.")
        return v


class ProveedorBase(BaseModel):
    nombre: str
    documento: Optional[str] = None
    celular: Optional[str] = None
    correo: Optional[str] = None


class ProveedorCreate(ProveedorBase, ProveedorValidado):
    pass


class ProveedorUpdate(ProveedorValidado):
    nombre: Optional[str] = None
    documento: Optional[str] = None
    celular: Optional[str] = None
    correo: Optional[str] = None


class ProveedorResponse(ProveedorBase):
    id: int

    class Config:
        from_attributes = True
