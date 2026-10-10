from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.db.models import Usuario
from app.api.deps import get_current_active_user
from app.schemas.producto import ProductoCreate, ProductoUpdate, ProductoResponse, KardexCreate, KardexResponse
from app.schemas.common import Pagina
from app.crud import crud_producto

router = APIRouter()

@router.post("/", response_model=ProductoResponse)
def crear_producto(producto: ProductoCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    db_producto = crud_producto.obtener_producto_por_codigo(db, codigo=producto.codigo)
    if db_producto:
        raise HTTPException(status_code=400, detail="Ya existe un producto con este código")
    return crud_producto.crear_producto(db=db, producto=producto, usuario_id=current_user.id)

@router.get("/", response_model=Pagina[ProductoResponse])
def leer_productos(skip: int = 0, limit: int = 50, buscar: Optional[str] = None, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    total, items = crud_producto.obtener_productos(db, skip=skip, limit=limit, buscar=buscar)
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.get("/{producto_id}", response_model=ProductoResponse)
def leer_producto(producto_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    db_producto = crud_producto.obtener_producto(db, producto_id=producto_id)
    if not db_producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return db_producto

@router.put("/{producto_id}", response_model=ProductoResponse)
def actualizar_producto(producto_id: int, producto: ProductoUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_producto.actualizar_producto(db=db, producto_id=producto_id, producto_in=producto)

@router.post("/{producto_id}/kardex", response_model=KardexResponse)
def registrar_movimiento_inventario(producto_id: int, kardex: KardexCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    # Útil para ingresos de nueva mercancía, ajustes manuales o devoluciones sin factura.
    return crud_producto.registrar_kardex(db=db, producto_id=producto_id, kardex_data=kardex, usuario_id=current_user.id)

@router.get("/{producto_id}/kardex", response_model=List[KardexResponse])
def historial_kardex(producto_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_producto.obtener_kardex_producto(db=db, producto_id=producto_id)
