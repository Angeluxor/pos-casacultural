from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import Optional
from datetime import date, datetime, time, timedelta

from app.db.session import get_db
from app.db.models import Usuario, Cliente, EstadoFactura
from app.api.deps import get_current_active_user, require_admin
from app.schemas.factura import (
    FacturaCreate,
    FacturaResponse,
    PagoCreate,
    FacturaAnular,
    FacturaClienteUpdate,
    ItemFacturaCreate,
    ItemFacturaUpdate,
)
from app.schemas.common import Pagina
from app.crud import crud_factura
from app.db.models import Factura
from app.core.timezone import BOGOTA_TZ

router = APIRouter()

@router.post("/", response_model=FacturaResponse)
def crear_factura(factura: FacturaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return crud_factura.crear_factura(db=db, factura_in=factura, vendedor_id=current_user.id)

@router.post("/{factura_id}/pagos", response_model=FacturaResponse)
def registrar_pagos(factura_id: int, pagos: PagoCreate | list[PagoCreate], db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    lista = pagos if isinstance(pagos, list) else [pagos]
    return crud_factura.registrar_pagos_factura(db=db, factura_id=factura_id, pagos=lista, cajero_id=current_user.id)

@router.get("/", response_model=Pagina[FacturaResponse])
def listar_facturas(
    skip: int = 0,
    limit: int = 30,
    buscar: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    query = db.query(Factura).options(selectinload(Factura.detalles), selectinload(Factura.pagos))
    if buscar:
        q = buscar.strip()
        filtro = f"%{q}%"
        query = query.join(Cliente, Factura.cliente_id == Cliente.id, isouter=True)
        cond = Cliente.nombre.ilike(filtro)
        if q.isdigit():
            try:
                cond = cond | (Factura.id == int(q))
            except ValueError:
                pass
        query = query.filter(cond)
    if estado:
        try:
            query = query.filter(Factura.estado == EstadoFactura(estado))
        except ValueError:
            pass
    if desde:
        try:
            d = date.fromisoformat(desde)
            query = query.filter(Factura.fecha >= datetime.combine(d, time.min, tzinfo=BOGOTA_TZ))
        except ValueError:
            pass
    if hasta:
        try:
            h = date.fromisoformat(hasta)
            query = query.filter(Factura.fecha < datetime.combine(h + timedelta(days=1), time.min, tzinfo=BOGOTA_TZ))
        except ValueError:
            pass
    total = query.count()
    items = query.order_by(Factura.id.desc()).offset(skip).limit(limit).all()
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.get("/{factura_id}", response_model=FacturaResponse)
def obtener_factura(factura_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    factura = (
        db.query(Factura)
        .options(selectinload(Factura.detalles), selectinload(Factura.pagos))
        .filter(Factura.id == factura_id)
        .first()
    )
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return factura


@router.put("/{factura_id}/cliente", response_model=FacturaResponse)
def asignar_cliente(
    factura_id: int,
    datos: FacturaClienteUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_factura.asignar_cliente_factura(
        db=db, factura_id=factura_id, cliente_id=datos.cliente_id
    )


@router.post("/{factura_id}/anular", response_model=FacturaResponse)
def anular_factura(
    factura_id: int,
    datos: FacturaAnular | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin),
):
    return crud_factura.anular_factura(
        db=db,
        factura_id=factura_id,
        usuario_id=current_user.id,
        motivo=datos.motivo if datos else None,
    )


@router.post("/{factura_id}/items", response_model=FacturaResponse)
def agregar_item(
    factura_id: int,
    item: ItemFacturaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_factura.agregar_item_factura(db, factura_id, item, current_user.id)


@router.put("/{factura_id}/items/{detalle_id}", response_model=FacturaResponse)
def actualizar_item(
    factura_id: int,
    detalle_id: int,
    item: ItemFacturaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_factura.actualizar_item_factura(db, factura_id, detalle_id, item, current_user.id)


@router.delete("/{factura_id}/items/{detalle_id}", response_model=FacturaResponse)
def eliminar_item(
    factura_id: int,
    detalle_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return crud_factura.eliminar_item_factura(db, factura_id, detalle_id, current_user.id)
