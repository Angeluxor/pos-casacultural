import re
from pydantic import BaseModel, field_validator
from typing import Optional


CELULAR_RE = re.compile(r"\d{7,15}")
CORREO_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class ClienteValidado(BaseModel):
    @field_validator("celular", check_fields=False)
    @classmethod
    def validar_celular(cls, v):
        if v is None or v == "":
            return v
        if not CELULAR_RE.fullmatch(v):
            raise ValueError("El celular debe contener solo números (7 a 15 dígitos).")
        return v

    @field_validator("correo", check_fields=False)
    @classmethod
    def validar_correo(cls, v):
        if v is None or v == "":
            return v
        if not CORREO_RE.fullmatch(v):
            raise ValueError("El correo no tiene un formato válido.")
        return v


class ClienteBase(BaseModel):
    nombre: str
    documento: Optional[str] = None
    celular: Optional[str] = None
    correo: Optional[str] = None


class ClienteCreate(ClienteBase, ClienteValidado):
    pass


class ClienteUpdate(ClienteValidado):
    nombre: Optional[str] = None
    documento: Optional[str] = None
    celular: Optional[str] = None
    correo: Optional[str] = None


class ClienteResponse(ClienteBase):
    id: int

    class Config:
        from_attributes = True
