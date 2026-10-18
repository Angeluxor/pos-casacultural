from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import require_permiso
from app.schemas.cliente import ClienteCreate, ClienteUpdate, ClienteResponse
from app.schemas.common import Pagina
from app.crud import crud_cliente

router = APIRouter()

@router.post("/", response_model=ClienteResponse)
def crear_cliente(cliente: ClienteCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("clientes.crear"))):
    if cliente.documento:
        db_cliente = crud_cliente.obtener_cliente_por_documento(db, documento=cliente.documento)
        if db_cliente:
            raise HTTPException(status_code=400, detail="Ya existe un cliente con este documento")
    return crud_cliente.crear_cliente(db=db, cliente=cliente)

@router.get("/", response_model=Pagina[ClienteResponse])
def leer_clientes(skip: int = 0, limit: int = 50, buscar: Optional[str] = None, orden: Optional[str] = None, direccion: Optional[str] = None, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("clientes.ver"))):
    total, items = crud_cliente.obtener_clientes(db, skip=skip, limit=limit, buscar=buscar, orden=orden, direccion=direccion)
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.get("/{cliente_id}", response_model=ClienteResponse)
def leer_cliente(cliente_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("clientes.ver"))):
    db_cliente = crud_cliente.obtener_cliente(db, cliente_id=cliente_id)
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return db_cliente

@router.put("/{cliente_id}", response_model=ClienteResponse)
def actualizar_cliente(cliente_id: int, cliente: ClienteUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("clientes.editar"))):
    if cliente.documento:
        existente = crud_cliente.obtener_cliente_por_documento(db, documento=cliente.documento)
        if existente and existente.id != cliente_id:
            raise HTTPException(status_code=400, detail="Ya existe otro cliente con este documento")
    return crud_cliente.actualizar_cliente(db=db, cliente_id=cliente_id, cliente_in=cliente)

@router.delete("/{cliente_id}", status_code=204)
def eliminar_cliente(cliente_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("clientes.eliminar"))):
    crud_cliente.eliminar_cliente(db=db, cliente_id=cliente_id)
    return None
