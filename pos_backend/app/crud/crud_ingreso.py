"""Registro de ingresos de inventario (compras / recepciones).

Un ingreso tiene una cabecera (proveedor, forma de pago, total declarado) y N
líneas que pueden ser: un producto existente, un producto nuevo (se crea con
código autogenerado) o un ítem libre de tipo "Otros". El total es obligatorio y
no se edita; el estado se deriva de cuánto se conoce de las líneas.

Un ingreso puede registrarse desde la caja activa o directamente en el balance
general:

- **Caja activa**: exige turno abierto. Efectivo/Transferencia descuentan de la
  caja del turno (salida al proveedor); Crédito y Donación no mueven dinero.
- **Balance general**: no exige caja ni mueve efectivo/banco. Efectivo y
  Transferencia se consideran pagados por fuera del POS; Crédito queda como
  cuenta por pagar y Donación no genera deuda.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.core.orden import ordenar
from app.core.categorias_caja import (
    CATEGORIA_COMPRA_INVENTARIO,
    CATEGORIA_DEVOLUCION,
    CATEGORIA_PAGO_PROVEEDOR,
)
from app.db.models import (
    EstadoIngreso,
    FormaPago,
    FormaPagoIngreso,
    FuentePagoIngreso,
    IngresoInventario,
    IngresoInventarioItem,
    Kardex,
    Producto,
    Proveedor,
    RegistroCaja,
    TipoItemIngreso,
    TipoMovimientoCaja,
    TipoMovimientoInventario,
    TurnoCaja,
)
from app.schemas.ingreso import IngresoCreate, IngresoUpdate, PagarIngreso
from app.crud import crud_proveedor

# Formas de pago del ingreso que mueven dinero en la caja del turno.
FORMAS_CON_CAJA = {FormaPagoIngreso.EFECTIVO, FormaPagoIngreso.TRANSFERENCIA}
_FORMA_CAJA = {
    FormaPagoIngreso.EFECTIVO: FormaPago.EFECTIVO,
    FormaPagoIngreso.TRANSFERENCIA: FormaPago.TRANSFERENCIA,
}
# Formas con las que se puede pagar una compra a crédito.
FORMAS_PAGO_CREDITO = {FormaPago.EFECTIVO, FormaPago.TRANSFERENCIA}

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


def _normalizar_compra_producto(linea):
    """Resuelve una línea de producto comprada por unidad o por formato.

    Devuelve ``(cantidad_total, unidades_por_formato, costo_unitario)``. Si la
    línea trae ``cantidad_formatos`` (por ejemplo 2 cajas), la cantidad total
    se calcula multiplicando por ``unidades_por_formato`` (12). Si trae
    ``costo_formato`` (el costo de la caja), el unitario se calcula dividiendo.
    Cuando no se envían datos de formato se mantiene el comportamiento
    anterior: ``cantidad`` y ``costo_unitario`` se usan tal cual.
    """
    factor = (
        linea.unidades_por_formato
        if linea.unidades_por_formato is not None
        else 1
    )
    if factor < 1:
        raise HTTPException(
            status_code=400,
            detail="Las unidades por caja o paquete deben ser mayores a 0.",
        )

    cantidad = linea.cantidad or 0
    if linea.cantidad_formatos is not None:
        if linea.cantidad_formatos <= 0:
            raise HTTPException(
                status_code=400,
                detail="La cantidad de cajas o paquetes debe ser mayor a 0.",
            )
        cantidad = linea.cantidad_formatos * factor
    if cantidad <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad de cada producto debe ser mayor a 0.",
        )

    costo = linea.costo_unitario
    if linea.costo_formato is not None:
        if linea.costo_formato < 0:
            raise HTTPException(
                status_code=400,
                detail="El costo de la caja o paquete no puede ser negativo.",
            )
        # Se conservan cuatro decimales para no perder centavos al dividir
        # una caja entre muchas unidades.
        costo = round(linea.costo_formato / factor, 4)

    return cantidad, factor, costo


def _calcular_estado(items, total: float) -> EstadoIngreso:
    suma = round(sum(i.valor or 0.0 for i in items), 2)
    faltan_costos = any(i.valor is None for i in items)
    if suma - total > _TOLERANCIA:
        return EstadoIngreso.INCONSISTENTE
    if faltan_costos or total - suma > _TOLERANCIA:
        return EstadoIngreso.PARCIAL
    return EstadoIngreso.COMPLETO


def _obtener_o_404(db: Session, ingreso_id: int) -> IngresoInventario:
    ingreso = (
        db.query(IngresoInventario)
        .options(joinedload(IngresoInventario.proveedor_rel))
        .filter(IngresoInventario.id == ingreso_id)
        .first()
    )
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

    cantidad, factor, costo_unitario = _normalizar_compra_producto(linea)
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
            # Si se compra por caja/paquete y se vende por unidad, la unidad
            # de compra y la de venta no son la misma.
            misma_unidad_compra_venta=factor == 1,
        )
        db.add(producto)
        db.flush()

    _entrada_compra(db, producto, cantidad, usuario_id, referencia)
    es_formato = factor > 1
    valor = _valor_linea(linea.tipo, cantidad, costo_unitario)
    if (
        es_formato
        and linea.cantidad_formatos is not None
        and linea.costo_formato is not None
    ):
        # El valor de la compra es exactamente lo que se pagó por los
        # formatos, sin depender del redondeo del costo unitario.
        valor = round(linea.cantidad_formatos * linea.costo_formato, 2)
    return IngresoInventarioItem(
        ingreso_id=ingreso.id,
        tipo=linea.tipo,
        producto_id=producto.id,
        concepto=linea.concepto.strip() if linea.concepto else None,
        cantidad=cantidad,
        cantidad_formatos=linea.cantidad_formatos if es_formato else None,
        unidades_por_formato=factor if es_formato else None,
        costo_formato=linea.costo_formato if es_formato else None,
        costo_unitario=costo_unitario,
        valor=valor,
    )


def crear_ingreso(
    db: Session,
    turno_caja_id: Optional[int],
    datos: IngresoCreate,
    usuario_id: int,
):
    if not datos.items:
        raise HTTPException(status_code=400, detail="El ingreso debe tener al menos un ítem.")

    # La fuente de pago decide si el ingreso se ata a un turno de caja. En modo
    # balance general no hay turno ni movimiento de caja, aunque la forma sea
    # efectivo o transferencia: se considera pagado por fuera del POS.
    usa_caja = datos.fuente_pago == FuentePagoIngreso.CAJA
    if usa_caja and turno_caja_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Debe abrir la caja para registrar un ingreso con fuente "
                "«Caja activa», o elegir «Balance general»."
            ),
        )
    if not usa_caja:
        turno_caja_id = None

    # Las compras de contado/transferencia y las donaciones no son cuentas por
    # pagar. Solo una compra a crédito nace pendiente de pago.
    es_credito = datos.forma_pago == FormaPagoIngreso.CREDITO
    forma_pago_pago = _FORMA_CAJA.get(datos.forma_pago)
    proveedor = crud_proveedor.resolver_proveedor(
        db, proveedor_id=datos.proveedor_id, nombre=datos.proveedor
    )
    ingreso = IngresoInventario(
        usuario_id=usuario_id,
        turno_caja_id=turno_caja_id,
        fuente_pago=datos.fuente_pago,
        proveedor_id=proveedor.id if proveedor else None,
        forma_pago=datos.forma_pago,
        total=datos.total,
        observacion=datos.observacion,
        estado=EstadoIngreso.PARCIAL,
        pagado=not es_credito,
        fecha_pago=get_colombia_time() if forma_pago_pago else None,
        pagado_por_id=usuario_id if forma_pago_pago else None,
        forma_pago_pago=forma_pago_pago,
    )
    db.add(ingreso)
    db.flush()

    for linea in datos.items:
        db.add(_crear_item(db, ingreso, linea, usuario_id))

    db.flush()
    db.refresh(ingreso)
    ingreso.estado = _calcular_estado(ingreso.items, ingreso.total)

    if usa_caja and datos.forma_pago in FORMAS_CON_CAJA:
        db.add(
            RegistroCaja(
                turno_caja_id=turno_caja_id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.SALIDA,
                referencia=f"Ingreso #{ingreso.id}",
                forma_pago=_FORMA_CAJA[datos.forma_pago],
                monto=datos.total,
                categoria=CATEGORIA_COMPRA_INVENTARIO,
                observacion=proveedor.nombre if proveedor else "Ingreso de inventario",
            )
        )

    db.commit()
    db.refresh(ingreso)
    return ingreso


def _movimiento_compra(db: Session, ingreso_id: int) -> Optional[RegistroCaja]:
    """Salida de caja generada automáticamente al registrar el ingreso."""
    return (
        db.query(RegistroCaja)
        .filter(
            RegistroCaja.referencia == f"Ingreso #{ingreso_id}",
            RegistroCaja.tipo == TipoMovimientoCaja.SALIDA,
        )
        .first()
    )


def _turno_abierto(db: Session) -> Optional[TurnoCaja]:
    return db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()  # noqa: E712


def _sincronizar_caja_ingreso(
    db: Session,
    ingreso: IngresoInventario,
    fuente: FuentePagoIngreso,
    forma: FormaPagoIngreso,
    usuario_id: int,
):
    """Mantiene coherente la salida de caja al corregir la cabecera.

    La fuente «Caja activa» con efectivo o transferencia genera una salida por
    el total. Si el usuario corrige la forma de pago o la fuente, se actualiza
    (o se elimina) ese movimiento. Por seguridad, no se toca un movimiento de
    un turno ya cerrado: en ese caso se pide registrar el ajuste manualmente.
    """
    desea_movimiento = fuente == FuentePagoIngreso.CAJA and forma in FORMAS_CON_CAJA
    existente = _movimiento_compra(db, ingreso.id)

    if desea_movimiento:
        forma_caja = _FORMA_CAJA[forma]
        if existente:
            if existente.forma_pago == forma_caja:
                return
            turno = (
                db.query(TurnoCaja)
                .filter(TurnoCaja.id == existente.turno_caja_id)
                .first()
            )
            if not turno or not turno.abierta:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "La caja donde se registró este ingreso ya está cerrada; "
                        "no se puede cambiar la forma de pago. Registra el ajuste "
                        "manualmente en la caja."
                    ),
                )
            existente.forma_pago = forma_caja
            return

        turno = None
        if ingreso.turno_caja_id:
            turno = (
                db.query(TurnoCaja)
                .filter(TurnoCaja.id == ingreso.turno_caja_id)
                .first()
            )
        if not turno or not turno.abierta:
            turno = _turno_abierto(db)
        if not turno:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Debe abrir la caja para registrar la salida del ingreso "
                    "con la nueva forma de pago."
                ),
            )
        db.add(
            RegistroCaja(
                turno_caja_id=turno.id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.SALIDA,
                referencia=f"Ingreso #{ingreso.id}",
                forma_pago=forma_caja,
                monto=ingreso.total,
                categoria=CATEGORIA_COMPRA_INVENTARIO,
                observacion=ingreso.proveedor or "Ingreso de inventario",
            )
        )
        ingreso.turno_caja_id = turno.id
        return

    if existente:
        turno = (
            db.query(TurnoCaja)
            .filter(TurnoCaja.id == existente.turno_caja_id)
            .first()
        )
        if not turno or not turno.abierta:
            raise HTTPException(
                status_code=400,
                detail=(
                    "La caja donde se registró este ingreso ya está cerrada; "
                    "no se puede cambiar la forma de pago. Registra el ajuste "
                    "manualmente en la caja."
                ),
            )
        db.delete(existente)

    if fuente == FuentePagoIngreso.BALANCE:
        ingreso.turno_caja_id = None
    elif ingreso.turno_caja_id is None:
        turno = _turno_abierto(db)
        if not turno:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Debe abrir la caja para registrar el ingreso con fuente "
                    "«Caja activa»."
                ),
            )
        ingreso.turno_caja_id = turno.id


def _aplicar_estado_pago(
    ingreso: IngresoInventario, forma: FormaPagoIngreso, usuario_id: int
):
    """Ajusta el control de pago cuando cambia la forma de pago."""
    if forma == FormaPagoIngreso.CREDITO:
        ingreso.pagado = False
        ingreso.fecha_pago = None
        ingreso.pagado_por_id = None
        ingreso.forma_pago_pago = None
    elif forma == FormaPagoIngreso.DONACION:
        ingreso.pagado = True
        ingreso.fecha_pago = None
        ingreso.pagado_por_id = None
        ingreso.forma_pago_pago = None
    else:
        ingreso.pagado = True
        ingreso.forma_pago_pago = _FORMA_CAJA[forma]
        if ingreso.fecha_pago is None:
            ingreso.fecha_pago = get_colombia_time()
        ingreso.pagado_por_id = usuario_id


def editar_ingreso(
    db: Session, ingreso_id: int, datos: IngresoUpdate, usuario_id: int
):
    ingreso = _obtener_o_404(db, ingreso_id)
    if ingreso.anulada:
        raise HTTPException(
            status_code=400, detail="No se puede editar un ingreso anulado."
        )
    if ingreso.forma_pago == FormaPagoIngreso.CREDITO and ingreso.pagado:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede editar un ingreso a crédito que ya fue pagado. "
                "Anúlalo y regístralo de nuevo si necesitas corregirlo."
            ),
        )

    proporciono_forma = "forma_pago" in datos.model_fields_set
    proporciono_fuente = "fuente_pago" in datos.model_fields_set
    nueva_forma = datos.forma_pago if proporciono_forma else ingreso.forma_pago
    nueva_fuente = datos.fuente_pago if proporciono_fuente else ingreso.fuente_pago
    if nueva_forma is None:
        raise HTTPException(status_code=400, detail="La forma de pago es obligatoria.")
    if nueva_fuente is None:
        raise HTTPException(status_code=400, detail="La fuente de pago es obligatoria.")

    # Si cambia la fuente o la forma de pago, el movimiento de caja debe
    # seguir representando el dinero que realmente salió (o dejó de salir).
    if proporciono_forma or proporciono_fuente:
        _sincronizar_caja_ingreso(db, ingreso, nueva_fuente, nueva_forma, usuario_id)
        ingreso.fuente_pago = nueva_fuente
    if proporciono_forma and nueva_forma != ingreso.forma_pago:
        _aplicar_estado_pago(ingreso, nueva_forma, usuario_id)
        ingreso.forma_pago = nueva_forma

    cambios = datos.model_dump(exclude_unset=True, exclude={"items", "forma_pago", "fuente_pago"})
    # El proveedor se resuelve aparte: se puede enviar el id de uno existente o
    # solo el nombre (se crea si no existe).
    proporciono_proveedor = bool({"proveedor_id", "proveedor"} & datos.model_fields_set)
    cambios.pop("proveedor_id", None)
    cambios.pop("proveedor", None)
    if proporciono_proveedor:
        proveedor = crud_proveedor.resolver_proveedor(
            db, proveedor_id=datos.proveedor_id, nombre=datos.proveedor
        )
        ingreso.proveedor_id = proveedor.id if proveedor else None
    for campo, valor in cambios.items():
        setattr(ingreso, campo, valor)

    if datos.items:
        por_id = {i.id: i for i in ingreso.items}
        for linea in datos.items:
            item = por_id.get(linea.id)
            if not item:
                raise HTTPException(status_code=404, detail=f"La línea {linea.id} no pertenece a este ingreso.")
            if item.tipo != TipoItemIngreso.OTROS:
                factor = item.unidades_por_formato or 1
                campos = linea.model_fields_set
                costo = item.costo_unitario
                if "costo_formato" in campos and linea.costo_formato is not None:
                    if factor < 1:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Las unidades por caja o paquete deben ser "
                                "mayores a 0."
                            ),
                        )
                    if linea.costo_formato < 0:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "El costo de la caja o paquete no puede ser "
                                "negativo."
                            ),
                        )
                    costo = round(linea.costo_formato / factor, 4)
                    item.costo_formato = linea.costo_formato
                elif "costo_unitario" in campos:
                    costo = linea.costo_unitario
                    # Mantiene coherente el costo del formato con el unitario
                    # cuando la línea se compró por caja o paquete.
                    if factor > 1 and costo is not None:
                        item.costo_formato = round(costo * factor, 2)
                    else:
                        item.costo_formato = None
                item.costo_unitario = costo
                if (
                    "costo_formato" in campos
                    and linea.costo_formato is not None
                    and item.cantidad_formatos is not None
                ):
                    item.valor = round(
                        item.cantidad_formatos * linea.costo_formato, 2
                    )
                else:
                    item.valor = _valor_linea(item.tipo, item.cantidad, costo)

    db.flush()
    db.refresh(ingreso)
    ingreso.estado = _calcular_estado(ingreso.items, ingreso.total)
    db.commit()
    db.refresh(ingreso)
    return ingreso


def pagar_ingreso(
    db: Session, ingreso_id: int, datos: PagarIngreso, usuario_id: int
):
    """Paga una compra a crédito y registra la salida de caja correspondiente.

    El pago se hace por el total del ingreso (no se manejan abonos parciales).
    Solo se permite efectivo o transferencia, y exige una caja abierta porque
    el dinero sale de uno de sus dos bolsillos.
    """
    ingreso = (
        db.query(IngresoInventario)
        .filter(IngresoInventario.id == ingreso_id)
        .with_for_update()
        .first()
    )
    if not ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")

    if ingreso.forma_pago != FormaPagoIngreso.CREDITO:
        raise HTTPException(
            status_code=400,
            detail="Solo las compras registradas como Crédito se pueden pagar.",
        )
    if ingreso.anulada:
        raise HTTPException(
            status_code=400, detail="No se puede pagar un ingreso anulado."
        )
    if ingreso.pagado:
        raise HTTPException(status_code=400, detail="Este ingreso ya está pagado.")
    if datos.forma_pago not in FORMAS_PAGO_CREDITO:
        raise HTTPException(
            status_code=400,
            detail="El pago de una compra a crédito debe ser en efectivo o transferencia.",
        )

    turno = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()  # noqa: E712
    if not turno:
        raise HTTPException(
            status_code=400,
            detail="Debe abrir la caja antes de pagar una compra a crédito.",
        )

    if (ingreso.total or 0) > 0:
        db.add(
            RegistroCaja(
                turno_caja_id=turno.id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.SALIDA,
                referencia=f"Pago ingreso #{ingreso.id}",
                forma_pago=datos.forma_pago,
                monto=ingreso.total,
                categoria=CATEGORIA_PAGO_PROVEEDOR,
                observacion=ingreso.proveedor or "Pago de compra a crédito",
            )
        )

    ingreso.pagado = True
    ingreso.fecha_pago = get_colombia_time()
    ingreso.pagado_por_id = usuario_id
    ingreso.forma_pago_pago = datos.forma_pago
    db.commit()
    db.refresh(ingreso)
    return ingreso


def resolver_ingreso(db: Session, ingreso_id: int, justificacion: str):
    ingreso = _obtener_o_404(db, ingreso_id)
    if ingreso.anulada:
        raise HTTPException(
            status_code=400, detail="No se puede resolver un ingreso anulado."
        )
    if ingreso.estado != EstadoIngreso.INCONSISTENTE:
        raise HTTPException(status_code=400, detail="Solo se pueden resolver los ingresos inconsistentes.")
    if not justificacion.strip():
        raise HTTPException(status_code=400, detail="Debes indicar una justificación.")
    ingreso.estado = EstadoIngreso.COMPLETO
    ingreso.justificacion = justificacion.strip()
    db.commit()
    db.refresh(ingreso)
    return ingreso


def anular_ingreso(db: Session, ingreso_id: int, motivo: str, usuario_id: int):
    """Anula un ingreso y revierte sus efectos operativos.

    El registro se conserva (no se borra) para auditoría. Se devuelve el stock
    al proveedor y, si el ingreso había movido caja, se registra una entrada
    por el mismo valor en el turno abierto. Si no hay caja abierta y hay dinero
    que devolver, la operación se rechaza.
    """
    ingreso = (
        db.query(IngresoInventario)
        .filter(IngresoInventario.id == ingreso_id)
        .with_for_update()
        .first()
    )
    if not ingreso:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    if ingreso.anulada:
        raise HTTPException(status_code=400, detail="Este ingreso ya está anulado.")

    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(
            status_code=400, detail="Debes indicar el motivo de la anulación."
        )

    # Se valida primero si hay dinero que devolver y si existe una caja
    # abierta, para no revertir stock y luego fallar a mitad de camino.
    movimientos = (
        db.query(RegistroCaja)
        .filter(
            RegistroCaja.referencia.in_(
                [f"Ingreso #{ingreso.id}", f"Pago ingreso #{ingreso.id}"]
            ),
            RegistroCaja.tipo == TipoMovimientoCaja.SALIDA,
        )
        .all()
    )
    turno_devolucion = None
    if movimientos:
        turno_devolucion = _turno_abierto(db)
        if not turno_devolucion:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No hay una caja abierta para devolver el dinero de este "
                    "ingreso. Abre la caja y vuelve a intentarlo."
                ),
            )

    # 1. Revertir el stock que entró con la compra.
    for item in ingreso.items:
        if not item.producto_id or not item.cantidad:
            continue
        producto = (
            db.query(Producto)
            .filter(Producto.id == item.producto_id)
            .with_for_update()
            .first()
        )
        if not producto:
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró el producto #{item.producto_id} para revertir el stock.",
            )
        disponible = producto.stock or 0
        if disponible < item.cantidad:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No se puede anular: el producto «{producto.nombre}» ya no "
                    f"tiene stock suficiente (disponible {disponible}, comprado "
                    f"{item.cantidad}). Ajusta el inventario primero."
                ),
            )
        producto.stock = disponible - item.cantidad
        db.add(
            Kardex(
                producto_id=producto.id,
                usuario_id=usuario_id,
                tipo_movimiento=TipoMovimientoInventario.SALIDA_ANULACION,
                cantidad=item.cantidad,
                saldo_stock=producto.stock,
                referencia=f"Anulación Ingreso #{ingreso.id}",
            )
        )

    # 2. Devolver el dinero que había salido de la caja (compra de contado o
    # pago posterior de una compra a crédito).
    for movimiento in movimientos:
        db.add(
            RegistroCaja(
                turno_caja_id=turno_devolucion.id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.ENTRADA,
                referencia=f"Anulación Ingreso #{ingreso.id}",
                forma_pago=movimiento.forma_pago,
                monto=movimiento.monto,
                categoria=CATEGORIA_DEVOLUCION,
                observacion=f"{motivo} · {movimiento.referencia}",
            )
        )

    ingreso.anulada = True
    ingreso.motivo_anulacion = motivo
    ingreso.fecha_anulacion = get_colombia_time()
    ingreso.anulada_por_id = usuario_id

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
    query = (
        db.query(IngresoInventario)
        .outerjoin(Proveedor, IngresoInventario.proveedor_id == Proveedor.id)
        .options(contains_eager(IngresoInventario.proveedor_rel))
    )
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
                "proveedor": Proveedor.nombre,
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