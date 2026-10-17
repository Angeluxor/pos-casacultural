"""Registro de ingresos de inventario (compras / recepciones).

Un ingreso tiene una cabecera (proveedor, forma de pago, total declarado) y N
líneas que pueden ser: un producto existente, un producto nuevo (se crea con
código autogenerado) o un ítem libre de tipo "Otros". El total es obligatorio y
no se edita; el estado se deriva de cuánto se conoce de las líneas.

Los ingresos quedan atados al turno de caja abierto. Solo las formas de pago
Efectivo y Transferencia generan un movimiento de caja (Crédito y Donación no).
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timezone import BOGOTA_TZ
from app.core.orden import ordenar
from app.db.models import (
    EstadoIngreso,
    FormaPago,
    FormaPagoIngreso,
    IngresoInventario,
    IngresoInventarioItem,
    Kardex,
    Producto,
    RegistroCaja,
    TipoItemIngreso,
    TipoMovimientoCaja,
    TipoMovimientoInventario,
)
from app.schemas.ingreso import IngresoCreate, IngresoUpdate

# Formas de pago del ingreso que mueven dinero en la caja del turno.
FORMAS_CON_CAJA = {FormaPagoIngreso.EFECTIVO, FormaPagoIngreso.TRANSFERENCIA}
_FORMA_CAJA = {
    FormaPagoIngreso.EFECTIVO: FormaPago.EFECTIVO,
    FormaPagoIngreso.TRANSFERENCIA: FormaPago.TRANSFERENCIA,
}

# Diferencia de centavos tolerada al comparar la suma de líneas con el total.
_TOLERANCIA = 0.01


def _generar_codigo(db: Session) -> str:
    """Código autogenerado y único para los productos creados desde un ingreso."""
    numero = db.query(func.count(Producto.id)).scalar() or 0
    while True:
        numero += 1
        codigo = f"INV{numero:04d}"
        existe = db.query(Producto.id).filter(Producto.codigo == codigo).first()
        if not existe:
            return codigo


def _valor_linea(tipo: TipoItemIngreso, cantidad: Optional[int], costo: Optional[float]):
    """Valor de una línea de producto: costo * cantidad (nulo si no hay costo)."""
    if tipo == TipoItemIngreso.OTROS or costo is None:
        return None
    return round((cantidad or 0) * costo, 2)


def _calcular_estado(items, total: float) -> EstadoIngreso:
    suma = round(sum(i.valor or 0.0 for i in items), 2)
    faltan_costos = any(i.valor is None for i in items)
    if suma - total > _TOLERANCIA:
        return EstadoIngreso.INCONSISTENTE
    if faltan_costos or total - suma > _TOLERANCIA:
        return EstadoIngreso.PARCIAL
    return EstadoIngreso.COMPLETO


def _obtener_o_404(db: Session, ingreso_id: int) -> IngresoInventario:
    ingreso = db.query(IngresoInventario).filter(IngresoInventario.id == ingreso_id).first()
    if not ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    return ingreso


def _entrada_compra(db: Session, producto: Producto, cantidad: int, usuario_id: int, referencia: str):
    """Suma stock y registra el movimiento de kardex sin hacer commit."""
    producto.stock = (producto.stock or 0) + cantidad
    db.add(
        Kardex(
            producto_id=producto.id,
            usuario_id=usuario_id,
            tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
            cantidad=cantidad,
            saldo_stock=producto.stock,
            referencia=referencia,
        )
    )


def _crear_item(db: Session, ingreso: IngresoInventario, linea, usuario_id: int):
    referencia = f"Ingreso #{ingreso.id}"

    if linea.tipo == TipoItemIngreso.OTROS:
        if not (linea.concepto or "").strip():
            raise HTTPException(status_code=400, detail="El ítem 'Otros' necesita un concepto.")
        if linea.valor is None or linea.valor <= 0:
            raise HTTPException(status_code=400, detail="El ítem 'Otros' necesita un valor mayor a 0.")
        return IngresoInventarioItem(
            ingreso_id=ingreso.id,
            tipo=linea.tipo,
            concepto=linea.concepto.strip(),
            valor=linea.valor,
        )

    cantidad = linea.cantidad or 0
    if cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad de cada producto debe ser mayor a 0.")

    if linea.tipo == TipoItemIngreso.PRODUCTO:
        if not linea.producto_id:
            raise HTTPException(status_code=400, detail="Falta el producto de una de las líneas.")
        producto = db.query(Producto).filter(Producto.id == linea.producto_id).first()
        if not producto:
            raise HTTPException(status_code=404, detail=f"Producto {linea.producto_id} no encontrado.")
    else:  # PRODUCTO_NUEVO
        if not (linea.concepto or "").strip():
            raise HTTPException(status_code=400, detail="El producto nuevo necesita un nombre.")
        if linea.precio is None or linea.precio < 0:
            raise HTTPException(status_code=400, detail="El producto nuevo necesita un precio.")
        producto = Producto(
            codigo=_generar_codigo(db),
            nombre=linea.concepto.strip(),
            precio=linea.precio,
            stock=0,
        )
        db.add(producto)
        db.flush()

    _entrada_compra(db, producto, cantidad, usuario_id, referencia)
    return IngresoInventarioItem(
        ingreso_id=ingreso.id,
        tipo=linea.tipo,
        producto_id=producto.id,
        concepto=linea.concepto.strip() if linea.concepto else None,
        cantidad=cantidad,
        costo_unitario=linea.costo_unitario,
        valor=_valor_linea(linea.tipo, cantidad, linea.costo_unitario),
    )


def crear_ingreso(db: Session, turno_caja_id: int, datos: IngresoCreate, usuario_id: int):
    if not datos.items:
        raise HTTPException(status_code=400, detail="El ingreso debe tener al menos un ítem.")

    ingreso = IngresoInventario(
        usuario_id=usuario_id,
        turno_caja_id=turno_caja_id,
        proveedor=datos.proveedor,
        forma_pago=datos.forma_pago,
        total=datos.total,
        observacion=datos.observacion,
        estado=EstadoIngreso.PARCIAL,
    )
    db.add(ingreso)
    db.flush()

    for linea in datos.items:
        db.add(_crear_item(db, ingreso, linea, usuario_id))

    db.flush()
    db.refresh(ingreso)
    ingreso.estado = _calcular_estado(ingreso.items, ingreso.total)

    if datos.forma_pago in FORMAS_CON_CAJA:
        db.add(
            RegistroCaja(
                turno_caja_id=turno_caja_id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.ENTRADA,
                referencia=f"Ingreso #{ingreso.id}",
                forma_pago=_FORMA_CAJA[datos.forma_pago],
                monto=datos.total,
                observacion=datos.proveedor or "Ingreso de inventario",
            )
        )

    db.commit()
    db.refresh(ingreso)
    return ingreso


def editar_ingreso(db: Session, ingreso_id: int, datos: IngresoUpdate):
    ingreso = _obtener_o_404(db, ingreso_id)

    cambios = datos.model_dump(exclude_unset=True, exclude={"items"})
    for campo, valor in cambios.items():
        setattr(ingreso, campo, valor)

    if datos.items:
        por_id = {i.id: i for i in ingreso.items}
        for linea in datos.items:
            item = por_id.get(linea.id)
            if not item:
                raise HTTPException(status_code=404, detail=f"La línea {linea.id} no pertenece a este ingreso.")
            if item.tipo != TipoItemIngreso.OTROS:
                item.costo_unitario = linea.costo_unitario
                item.valor = _valor_linea(item.tipo, item.cantidad, linea.costo_unitario)

    db.flush()
    db.refresh(ingreso)
    ingreso.estado = _calcular_estado(ingreso.items, ingreso.total)
    db.commit()
    db.refresh(ingreso)
    return ingreso


def resolver_ingreso(db: Session, ingreso_id: int, justificacion: str):
    ingreso = _obtener_o_404(db, ingreso_id)
    if ingreso.estado != EstadoIngreso.INCONSISTENTE:
        raise HTTPException(status_code=400, detail="Solo se pueden resolver los ingresos inconsistentes.")
    if not justificacion.strip():
        raise HTTPException(status_code=400, detail="Debes indicar una justificación.")
    ingreso.estado = EstadoIngreso.COMPLETO
    ingreso.justificacion = justificacion.strip()
    db.commit()
    db.refresh(ingreso)
    return ingreso


def obtener_ingreso(db: Session, ingreso_id: int):
    return _obtener_o_404(db, ingreso_id)


def obtener_ingresos(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
):
    query = db.query(IngresoInventario)
    if desde:
        try:
            d = date.fromisoformat(desde)
            query = query.filter(
                IngresoInventario.fecha >= datetime.combine(d, time.min, BOGOTA_TZ)
            )
        except ValueError:
            pass
    if hasta:
        try:
            h = date.fromisoformat(hasta)
            query = query.filter(
                IngresoInventario.fecha
                < datetime.combine(h + timedelta(days=1), time.min, BOGOTA_TZ)
            )
        except ValueError:
            pass

    total = query.count()
    items = (
        ordenar(
            query,
            orden,
            direccion,
            {
                "id": IngresoInventario.id,
                "fecha": IngresoInventario.fecha,
                "proveedor": IngresoInventario.proveedor,
                "forma_pago": IngresoInventario.forma_pago,
                "total": IngresoInventario.total,
                "estado": IngresoInventario.estado,
            },
            [IngresoInventario.id.desc()],
            desempate=IngresoInventario.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items