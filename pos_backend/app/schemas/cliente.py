from pydantic import BaseModel
from typing import Optional


class ClienteBase(BaseModel):
    nombre: str
    documento: str


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    documento: Optional[str] = None


class ClienteResponse(ClienteBase):
    id: int

    class Config:
        from_attributes = True
