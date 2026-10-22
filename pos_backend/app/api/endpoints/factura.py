from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import case, func
from typing import Optional
from datetime import date, datetime, time, timedelta

from app.db.session import get_db
from app.db.models import Usuario, Cliente, EstadoFactura
from app.api.deps import require_permiso
from app.schemas.factura import (
    FacturaCreate,
    FacturaResponse,
    PagoCreate,
    FacturaAnular,
    FacturaClienteUpdate,
    ItemFacturaCreate,
    ItemFacturaUpdate,
    PaginaFacturas,
    TotalesFacturas,
)
from app.crud import crud_factura
from app.db.models import Factura
from app.core.timezone import BOGOTA_TZ
from app.core.orden import ordenar

router = APIRouter()

@router.post("/", response_model=FacturaResponse)
def crear_factura(
    factura: FacturaCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.crear")),
):
    return crud_factura.crear_factura(
        db=db,
        factura_in=factura,
        vendedor_id=current_user.id,
        clave_idempotencia=idempotency_key,
    )

@router.post("/{factura_id}/pagos", response_model=FacturaResponse)
def registrar_pagos(
    factura_id: int,
    pagos: PagoCreate | list[PagoCreate],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.cobrar")),
):
    lista = pagos if isinstance(pagos, list) else [pagos]
    return crud_factura.registrar_pagos_factura(
        db=db,
        factura_id=factura_id,
        pagos=lista,
        cajero_id=current_user.id,
        clave_idempotencia=idempotency_key,
    )

@router.get("/", response_model=PaginaFacturas)
def listar_facturas(
    skip: int = 0,
    limit: int = 30,
    buscar: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    estado: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.ver")),
):
    query = db.query(Factura)
    # Necesitamos la tabla clientes si se busca por nombre o se ordena por cliente.
    if buscar or orden == "cliente":
        query = query.join(Cliente, Factura.cliente_id == Cliente.id, isouter=True)
    if buscar:
        q = buscar.strip()
        filtro = f"%{q}%"
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
    total_facturado, total_saldo, total_anulado, facturas_anuladas = (
        query.with_entities(
            func.coalesce(func.sum(Factura.total), 0.0),
            func.coalesce(func.sum(Factura.saldo), 0.0),
            func.coalesce(
                func.sum(
                    case(
                        (Factura.estado == EstadoFactura.ANULADA, Factura.total),
                        else_=0.0,
                    )
                ),
                0.0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Factura.estado == EstadoFactura.ANULADA, 1),
                        else_=0,
                    )
                ),
                0,
            ),
        ).one()
    )
    items = (
        ordenar(
            query.options(selectinload(Factura.detalles), selectinload(Factura.pagos)),
            orden,
            direccion,
            {
                "id": Factura.id,
                "fecha": Factura.fecha,
                # El nombre a mostrar es el eventual si existe; si no, el del cliente.
                "cliente": func.coalesce(Factura.nombre_eventual, Cliente.nombre),
                "total": Factura.total,
                "saldo": Factura.saldo,
                "estado": Factura.estado,
            },
            [Factura.id.desc()],
            desempate=Factura.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return PaginaFacturas(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        totales=TotalesFacturas(
            total_facturado=float(total_facturado),
            saldo=float(total_saldo),
            total_anulado=float(total_anulado),
            neto=round(float(total_facturado) - float(total_anulado), 2),
            facturas_anuladas=int(facturas_anuladas or 0),
        ),
    )

@router.get("/{factura_id}", response_model=FacturaResponse)
def obtener_factura(factura_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("ventas.ver"))):
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
    current_user: Usuario = Depends(require_permiso("ventas.editar")),
):
    return crud_factura.asignar_cliente_factura(
        db=db, factura_id=factura_id, cliente_id=datos.cliente_id
    )


@router.post("/{factura_id}/anular", response_model=FacturaResponse)
def anular_factura(
    factura_id: int,
    datos: FacturaAnular | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.anular")),
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
    current_user: Usuario = Depends(require_permiso("ventas.editar")),
):
    return crud_factura.agregar_item_factura(db, factura_id, item, current_user.id)


@router.put("/{factura_id}/items/{detalle_id}", response_model=FacturaResponse)
def actualizar_item(
    factura_id: int,
    detalle_id: int,
    item: ItemFacturaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.editar")),
):
    return crud_factura.actualizar_item_factura(db, factura_id, detalle_id, item, current_user.id)


@router.delete("/{factura_id}/items/{detalle_id}", response_model=FacturaResponse)
def eliminar_item(
    factura_id: int,
    detalle_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("ventas.editar")),
):
    return crud_factura.eliminar_item_factura(db, factura_id, detalle_id, current_user.id)
