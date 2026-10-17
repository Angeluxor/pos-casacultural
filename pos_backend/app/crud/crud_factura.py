from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db.models import (
    Factura, DetalleFactura, Producto, TurnoCaja, RegistroCaja,
    Pago, Cliente, EstadoFactura, FormaPago, TipoMovimientoInventario, Kardex, TipoMovimientoCaja
)
from app.core.timezone import get_colombia_time
from app.crud import crud_cliente
from app.schemas.factura import FacturaCreate, PagoCreate, ItemFacturaCreate, ItemFacturaUpdate

def crear_factura(db: Session, factura_in: FacturaCreate, vendedor_id: int):
    # El cliente eventual (reemplazo de "Consumidor final") se usa cuando no se
    # selecciona un cliente real; el nombre temporal queda como texto.
    nombre_eventual = (factura_in.nombre_eventual or "").strip() or None
    if factura_in.cliente_id:
        cliente_id = factura_in.cliente_id
        nombre_eventual = None
    else:
        cliente_id = crud_cliente.obtener_o_crear_cliente_eventual(db).id

    # La venta queda atada al turno de caja abierto (si lo hay) para el paso a
    # crédito al cerrar caja.
    caja_abierta = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()

    # 1. Crear la cabecera de la factura primero para obtener un ID temporal
    db_factura = Factura(
        cliente_id=cliente_id,
        vendedor_id=vendedor_id,
        nombre_eventual=nombre_eventual,
        turno_caja_id=caja_abierta.id if caja_abierta else None,
        estado=EstadoFactura.ABIERTA,
        total=0,
        saldo=0
    )
    db.add(db_factura)
    db.flush() # Envía a la base de datos pero NO hace commit aún (Transaction ACID)
    
    total_factura = 0.0
    
    for detalle_in in factura_in.detalles:
        # Usamos with_for_update() para bloquear la fila y evitar problemas de concurrencia al vender
        producto = db.query(Producto).filter(Producto.id == detalle_in.producto_id).with_for_update().first()
        
        if not producto:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Producto con ID {detalle_in.producto_id} no encontrado")
            
        if producto.stock < detalle_in.cantidad:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para el producto: {producto.nombre}. Disponible: {producto.stock}")
            
        subtotal = producto.precio * detalle_in.cantidad
        total_factura += subtotal
        
        # 2. Agregar Detalle
        db_detalle = DetalleFactura(
            factura_id=db_factura.id,
            producto_id=producto.id,
            cantidad=detalle_in.cantidad,
            precio_unitario=producto.precio,
            subtotal=subtotal
        )
        db.add(db_detalle)
        
        # 3. Restar stock real
        producto.stock -= detalle_in.cantidad
        
        # 4. Generar el registro en Kardex por la salida
        db_kardex = Kardex(
            producto_id=producto.id,
            usuario_id=vendedor_id,
            tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
            cantidad=detalle_in.cantidad,
            saldo_stock=producto.stock,
            referencia=f"Venta en Factura #{db_factura.id}"
        )
        db.add(db_kardex)
        
    db_factura.total = total_factura
    db_factura.saldo = total_factura # El saldo inicial adeudado es el total
    
    db.commit() # ¡Éxito! Todo se guarda simultáneamente (Factura + Detalles + Stock + Kardex)
    db.refresh(db_factura)
    return db_factura


def registrar_pagos_factura(db: Session, factura_id: int, pagos: list[PagoCreate], cajero_id: int):
    """Registra uno o varios pagos (medios de pago combinados) sobre una factura."""
    if not pagos:
        raise HTTPException(status_code=400, detail="Debe registrar al menos un pago.")

    # 1. Verificar si hay Caja Abierta
    caja_abierta = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
    if not caja_abierta:
        raise HTTPException(status_code=400, detail="No se pueden registrar pagos. No hay una caja abierta actualmente.")

    # 2. Buscar factura (con bloqueo de fila)
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if factura.estado in [EstadoFactura.PAGADA, EstadoFactura.ANULADA]:
        db.rollback()
        raise HTTPException(status_code=400, detail="La factura ya se encuentra pagada o está anulada.")

    for pago in pagos:
        if pago.valor <= 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="Cada pago debe ser mayor a 0.")

    total = round(sum(pago.valor for pago in pagos), 2)
    if total > factura.saldo:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"El valor total de los pagos ({total}) excede el saldo pendiente ({factura.saldo})")

    # 3. Registrar cada pago y su entrada de caja
    for pago in pagos:
        db.add(Pago(
            factura_id=factura.id,
            cajero_id=cajero_id,
            valor=pago.valor,
            forma_pago=pago.forma_pago
        ))
        db.add(RegistroCaja(
            turno_caja_id=caja_abierta.id,
            usuario_id=cajero_id,
            tipo=TipoMovimientoCaja.ENTRADA,
            referencia=f"Abono a Factura #{factura.id}",
            forma_pago=pago.forma_pago,
            monto=pago.valor,
            observacion="Cobro de ventas"
        ))

    # 4. Actualizar Saldos y Estados
    factura.saldo = round(factura.saldo - total, 2)
    if factura.saldo <= 0: # Check robusto
        factura.estado = EstadoFactura.PAGADA
        factura.saldo = 0
    else:
        factura.estado = EstadoFactura.PAGADO_PARCIAL

    db.commit() # Atomicidad: Pago + Flujo de Caja + Actualización de Factura
    db.refresh(factura)
    return factura


def registrar_pago_factura(db: Session, factura_id: int, pago_in: PagoCreate, cajero_id: int):
    """Compatibilidad: registra un único pago."""
    return registrar_pagos_factura(db, factura_id, [pago_in], cajero_id)


def anular_factura(db: Session, factura_id: int, usuario_id: int, motivo: str | None = None):
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if factura.estado == EstadoFactura.ANULADA:
        db.rollback()
        raise HTTPException(status_code=400, detail="La factura ya está anulada.")

    total_pagado = sum(pago.valor for pago in factura.pagos)

    # Si ya se cobró dinero, la anulación debe devolverlo desde la caja abierta
    caja_abierta = None
    if total_pagado > 0:
        caja_abierta = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
        if not caja_abierta:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="No hay una caja abierta para registrar la devolución del dinero cobrado.",
            )

    # 1. Devolver el stock y registrar el kardex por la devolución
    for detalle in factura.detalles:
        # Los productos ya retirados de la factura devolvieron su stock al momento
        # del retiro; no se vuelven a reintegrar al anular.
        if detalle.anulado:
            continue
        producto = (
            db.query(Producto)
            .filter(Producto.id == detalle.producto_id)
            .with_for_update()
            .first()
        )
        if not producto:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró el producto ID {detalle.producto_id} para devolver stock",
            )
        producto.stock += detalle.cantidad
        db.add(
            Kardex(
                producto_id=producto.id,
                usuario_id=usuario_id,
                tipo_movimiento=TipoMovimientoInventario.DEVOLUCION,
                cantidad=detalle.cantidad,
                saldo_stock=producto.stock,
                referencia=f"Anulación Factura #{factura.id}",
            )
        )

    # 2. Devolver el dinero cobrado (salida de caja), separado por forma de pago
    if total_pagado > 0 and caja_abierta:
        por_forma: dict[FormaPago, float] = {}
        for pago in factura.pagos:
            por_forma[pago.forma_pago] = por_forma.get(pago.forma_pago, 0.0) + pago.valor
        for forma_pago, monto in por_forma.items():
            db.add(
                RegistroCaja(
                    turno_caja_id=caja_abierta.id,
                    usuario_id=usuario_id,
                    tipo=TipoMovimientoCaja.SALIDA,
                    referencia=f"Anulación Factura #{factura.id}",
                    forma_pago=forma_pago,
                    monto=monto,
                    observacion=motivo or "Devolución por anulación de venta",
                )
            )

    # 3. Marcar la factura como anulada y guardar la traza
    factura.estado = EstadoFactura.ANULADA
    factura.saldo = 0
    factura.motivo_anulacion = motivo
    factura.fecha_anulacion = get_colombia_time()
    factura.anulada_por_id = usuario_id

    db.commit()
    db.refresh(factura)
    return factura


def _bloquear_factura_mutable(db: Session, factura_id: int) -> Factura:
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if factura.estado == EstadoFactura.ANULADA:
        db.rollback()
        raise HTTPException(status_code=400, detail="No se puede modificar una factura anulada.")
    return factura


def _mover_stock(
    db: Session,
    producto: Producto,
    delta: int,
    usuario_id: int,
    referencia: str,
):
    """delta > 0 devuelve stock (Devolución); delta < 0 descuenta stock (Salida por Venta)."""
    if delta == 0:
        return
    if delta < 0:
        cantidad = -delta
        if producto.stock < cantidad:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}",
            )
        producto.stock -= cantidad
        tipo = TipoMovimientoInventario.SALIDA_VENTA
    else:
        cantidad = delta
        producto.stock += cantidad
        tipo = TipoMovimientoInventario.DEVOLUCION

    db.add(
        Kardex(
            producto_id=producto.id,
            usuario_id=usuario_id,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            saldo_stock=producto.stock,
            referencia=referencia,
        )
    )


def _recalcular_factura(db: Session, factura: Factura, usuario_id: int):
    """Recalcula total/saldo/estado y reembolsa sobrepagos desde la caja abierta."""
    factura.total = round(sum(d.subtotal for d in factura.detalles if not d.anulado), 2)
    pagado = round(sum(p.valor for p in factura.pagos), 2)
    saldo = round(factura.total - pagado, 2)

    if saldo < 0:
        reembolso = -saldo
        caja = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
        if not caja:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Se debe devolver dinero al cliente, pero no hay una caja abierta.",
            )
        db.add(
            RegistroCaja(
                turno_caja_id=caja.id,
                usuario_id=usuario_id,
                tipo=TipoMovimientoCaja.SALIDA,
                referencia=f"Reembolso por modificación de venta #{factura.id}",
                forma_pago=FormaPago.EFECTIVO,
                monto=reembolso,
                observacion="Devolución por modificación de venta",
            )
        )
        saldo = 0

    factura.saldo = saldo
    if saldo <= 0:
        factura.estado = EstadoFactura.PAGADA
    elif pagado > 0:
        factura.estado = EstadoFactura.PAGADO_PARCIAL
    elif factura.estado == EstadoFactura.CREDITO:
        # Una factura ya marcada como crédito conserva ese estado al editarla.
        factura.estado = EstadoFactura.CREDITO
    else:
        factura.estado = EstadoFactura.ABIERTA


def agregar_item_factura(db: Session, factura_id: int, item_in: ItemFacturaCreate, usuario_id: int):
    if item_in.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")

    factura = _bloquear_factura_mutable(db, factura_id)

    producto = (
        db.query(Producto).filter(Producto.id == item_in.producto_id).with_for_update().first()
    )
    if not producto:
        db.rollback()
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    detalle = next(
        (d for d in factura.detalles if d.producto_id == producto.id and not d.anulado), None
    )
    if detalle:
        detalle.cantidad += item_in.cantidad
        detalle.subtotal = detalle.precio_unitario * detalle.cantidad
    else:
        detalle = DetalleFactura(
            producto_id=producto.id,
            cantidad=item_in.cantidad,
            precio_unitario=producto.precio,
            subtotal=producto.precio * item_in.cantidad,
        )
        factura.detalles.append(detalle)

    _mover_stock(db, producto, -item_in.cantidad, usuario_id, f"Adición a Factura #{factura.id}")
    _recalcular_factura(db, factura, usuario_id)

    db.commit()
    db.refresh(factura)
    return factura


def actualizar_item_factura(
    db: Session, factura_id: int, detalle_id: int, item_in: ItemFacturaUpdate, usuario_id: int
):
    if item_in.cantidad < 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa.")

    factura = _bloquear_factura_mutable(db, factura_id)

    detalle = (
        db.query(DetalleFactura)
        .filter(DetalleFactura.id == detalle_id, DetalleFactura.factura_id == factura_id)
        .first()
    )
    if not detalle:
        db.rollback()
        raise HTTPException(status_code=404, detail="El producto no está en esta factura.")

    if detalle.anulado:
        db.rollback()
        raise HTTPException(status_code=400, detail="El producto ya fue retirado de esta factura.")

    # En facturas pagadas o a crédito la cantidad solo puede aumentar: bajar o
    # retirar productos después del cobro/cierre no es válido.
    if factura.estado in (EstadoFactura.PAGADA, EstadoFactura.CREDITO):
        if item_in.cantidad == 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="No se pueden retirar productos de una factura pagada o a crédito.")
        if item_in.cantidad < detalle.cantidad:
            db.rollback()
            raise HTTPException(status_code=400, detail="En una factura pagada o a crédito solo se puede aumentar la cantidad.")

    if item_in.cantidad == 0:
        activos = [d for d in factura.detalles if not d.anulado]
        if len(activos) <= 1:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="La factura debe conservar al menos un producto activo. Para dejarla sin efecto usa Anular.",
            )
        producto = (
            db.query(Producto).filter(Producto.id == detalle.producto_id).with_for_update().first()
        )
        if producto:
            _mover_stock(db, producto, detalle.cantidad, usuario_id, f"Retiro de Factura #{factura.id}")
        # Persistimos la línea como retirada en vez de borrarla (traza de fraude).
        detalle.anulado = True
    else:
        diff = item_in.cantidad - detalle.cantidad
        if diff != 0:
            producto = (
                db.query(Producto)
                .filter(Producto.id == detalle.producto_id)
                .with_for_update()
                .first()
            )
            if not producto:
                db.rollback()
                raise HTTPException(status_code=404, detail="Producto no encontrado")
            _mover_stock(db, producto, -diff, usuario_id, f"Ajuste Factura #{factura.id}")
        detalle.cantidad = item_in.cantidad
        detalle.subtotal = detalle.precio_unitario * detalle.cantidad

    _recalcular_factura(db, factura, usuario_id)

    db.commit()
    db.refresh(factura)
    return factura


def eliminar_item_factura(db: Session, factura_id: int, detalle_id: int, usuario_id: int):
    factura = _bloquear_factura_mutable(db, factura_id)

    detalle = (
        db.query(DetalleFactura)
        .filter(DetalleFactura.id == detalle_id, DetalleFactura.factura_id == factura_id)
        .first()
    )
    if not detalle:
        db.rollback()
        raise HTTPException(status_code=404, detail="El producto no está en esta factura.")

    if detalle.anulado:
        db.rollback()
        raise HTTPException(status_code=400, detail="El producto ya fue retirado de esta factura.")

    if factura.estado in (EstadoFactura.PAGADA, EstadoFactura.CREDITO):
        db.rollback()
        raise HTTPException(status_code=400, detail="No se pueden retirar productos de una factura pagada o a crédito.")

    activos = [d for d in factura.detalles if not d.anulado]
    if len(activos) <= 1:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="La factura debe conservar al menos un producto activo. Para dejarla sin efecto usa Anular.",
        )

    producto = db.query(Producto).filter(Producto.id == detalle.producto_id).with_for_update().first()
    if producto:
        _mover_stock(db, producto, detalle.cantidad, usuario_id, f"Retiro de Factura #{factura.id}")

    # No se borra la línea: se marca como retirada para conservar la traza.
    detalle.anulado = True
    _recalcular_factura(db, factura, usuario_id)

    db.commit()
    db.refresh(factura)
    return factura


def asignar_cliente_factura(db: Session, factura_id: int, cliente_id: int):
    """Asigna un cliente real a una factura abierta (p. ej. para destrabar el cierre)."""
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if factura.estado == EstadoFactura.ANULADA:
        db.rollback()
        raise HTTPException(status_code=400, detail="No se puede modificar una factura anulada.")

    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        db.rollback()
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if cliente.es_eventual:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede asignar el cliente eventual como cliente real.",
        )

    factura.cliente_id = cliente.id
    # Al asignar un cliente real, el nombre temporal/eventual deja de aplicar.
    factura.nombre_eventual = None

    db.commit()
    db.refresh(factura)
    return factura
