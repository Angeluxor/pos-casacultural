from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int
