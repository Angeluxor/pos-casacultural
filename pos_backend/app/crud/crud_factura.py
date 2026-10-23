from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from fastapi import HTTPException
from datetime import datetime, timedelta
from app.db.models import (
    Factura, DetalleFactura, Producto, TurnoCaja, RegistroCaja,
    Pago, PagoIdempotente, OperacionFacturaIdempotente, Cliente,
    EstadoFactura, FormaPago, TipoMovimientoInventario, Kardex,
    TipoMovimientoCaja
)
from app.core.timezone import get_colombia_time
from app.core.categorias_caja import (
    CATEGORIA_VENTAS,
    CATEGORIA_DEVOLUCION,
)
from app.crud import crud_cliente
from app.schemas.factura import FacturaCreate, PagoCreate, ItemFacturaCreate, ItemFacturaUpdate

def _fecha_operacion(fecha: datetime | None) -> datetime:
    """Normaliza la fecha enviada por un POS offline y limita fechas futuras."""
    ahora = get_colombia_time()
    if fecha is None:
        return ahora
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=ahora.tzinfo)
    if fecha > ahora + timedelta(minutes=5):
        # Un reloj de dispositivo adelantado no debe bloquear una venta que ya
        # ocurrió. Se usa la hora del servidor y la operación queda registrada.
        return ahora
    return fecha

def _factura_con_relaciones(db: Session, factura_id: int) -> Factura:
    """Carga la factura con sus relaciones antes de serializar la respuesta.

    Evita *lazy loads* después del commit (cada uno es un viaje extra a la base
    de datos y, si la conexión se corta, la respuesta puede quedar colgada).
    """
    return (
        db.query(Factura)
        .options(
            selectinload(Factura.detalles),
            selectinload(Factura.pagos),
            joinedload(Factura.cliente),
        )
        .filter(Factura.id == factura_id)
        .one()
    )


def _buscar_factura_idempotente(
    db: Session, clave: str, vendedor_id: int
) -> Factura | None:
    factura = (
        db.query(Factura)
        .options(
            selectinload(Factura.detalles),
            selectinload(Factura.pagos),
            joinedload(Factura.cliente),
        )
        .filter(Factura.clave_idempotencia == clave)
        .first()
    )
    if factura and factura.vendedor_id != vendedor_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "Esa clave de idempotencia ya fue usada por otro usuario. "
                "No se registró ninguna venta nueva."
            ),
        )
    return factura


def crear_factura(
    db: Session,
    factura_in: FacturaCreate,
    vendedor_id: int,
    clave_idempotencia: str | None = None,
):
    # Un reintento del navegador (timeout, red móvil inestable, cold start)
    # reutiliza la misma clave. Si la venta ya se guardó, se devuelve tal cual
    # para no duplicar la factura ni volver a descontar stock.
    clave = (clave_idempotencia or "").strip() or None
    if clave and len(clave) > 64:
        raise HTTPException(
            status_code=400,
            detail="La clave de idempotencia no puede superar 64 caracteres.",
        )
    if clave:
        existente = _buscar_factura_idempotente(db, clave, vendedor_id)
        if existente:
            return existente

    # El cliente eventual (reemplazo de "Consumidor final") se usa cuando no se
    # selecciona un cliente real; el nombre temporal queda como texto.
    nombre_eventual = (factura_in.nombre_eventual or "").strip() or None
    if factura_in.cliente_id:
        cliente_id = factura_in.cliente_id
        nombre_eventual = None
    else:
        cliente_id = crud_cliente.obtener_o_crear_cliente_eventual(db).id

    # Turno y fecha de la operación. En una venta online se usa la caja abierta
    # y la hora del servidor; en una offline se conserva el turno y la hora del
    # dispositivo.
    notas_revision: list[str] = []
    turno_caja_id = None
    if factura_in.origen_offline and factura_in.turno_caja_id is not None:
        turno = (
            db.query(TurnoCaja)
            .filter(TurnoCaja.id == factura_in.turno_caja_id)
            .first()
        )
        if not turno:
            raise HTTPException(status_code=400, detail="Turno de caja no encontrado.")
        turno_caja_id = turno.id
        if not turno.abierta:
            notas_revision.append(
                f"La venta se sincronizó con el turno #{turno.id}, que ya estaba cerrado."
            )
    else:
        caja_abierta = (
            db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
        )
        turno_caja_id = caja_abierta.id if caja_abierta else None
        if factura_in.origen_offline and not turno_caja_id:
            notas_revision.append(
                "La venta offline no tenía un turno de caja abierto."
            )
    # Una venta online siempre usa la hora del servidor. La fecha del cliente
    # solo se conserva cuando la venta viene de la cola offline.
    fecha_factura = (
        _fecha_operacion(factura_in.fecha)
        if factura_in.origen_offline
        else get_colombia_time()
    )

    # 1. Crear la cabecera de la factura primero para obtener un ID temporal.
    db_factura = Factura(
        cliente_id=cliente_id,
        vendedor_id=vendedor_id,
        nombre_eventual=nombre_eventual,
        turno_caja_id=turno_caja_id,
        fecha=fecha_factura,
        estado=EstadoFactura.ABIERTA,
        total=0,
        saldo=0,
        clave_idempotencia=clave,
        origen="offline" if factura_in.origen_offline else "online",
    )
    db.add(db_factura)
    try:
        # Envía a la base de datos pero NO hace commit aún (Transaction ACID).
        db.flush()
    except IntegrityError:
        # Dos peticiones con la misma clave llegaron a la vez. La que perdió
        # la carrera devuelve la factura que sí se guardó.
        db.rollback()
        if clave:
            existente = _buscar_factura_idempotente(db, clave, vendedor_id)
            if existente:
                return existente
        # Otro error de integridad (p. ej. un cliente inexistente) no debe
        # disfrazarse de conflicto de concurrencia.
        raise

    # Bloquea todos los productos en un solo viaje y en orden de id (orden
    # estable). Antes se hacía una consulta por ítem, lo que multiplicaba la
    # latencia contra Neon y permitía interbloqueos si dos ventas tocaban los
    # mismos productos en orden distinto.
    productos: dict[int, Producto] = {}
    if factura_in.detalles:
        ids = {detalle.producto_id for detalle in factura_in.detalles}
        productos = {
            producto.id: producto
            for producto in (
                db.query(Producto)
                .filter(Producto.id.in_(ids))
                .order_by(Producto.id)
                .with_for_update()
                .all()
            )
        }

    total_factura = 0.0

    for detalle_in in factura_in.detalles:
        producto = productos.get(detalle_in.producto_id)

        if not producto:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail=f"Producto con ID {detalle_in.producto_id} no encontrado",
            )

        precio_unitario = producto.precio
        if factura_in.origen_offline and detalle_in.precio_unitario is not None:
            if detalle_in.precio_unitario < 0:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="El precio cobrado de cada producto no puede ser negativo.",
                )
            precio_unitario = detalle_in.precio_unitario

        if producto.stock < detalle_in.cantidad:
            if not factura_in.origen_offline:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Stock insuficiente para el producto: {producto.nombre}. "
                        f"Disponible: {producto.stock}"
                    ),
                )
            # Una venta offline ya ocurrió físicamente. No se rechaza: se deja
            # el stock negativo y se marca la factura para revisión.
            notas_revision.append(
                f"Stock insuficiente de {producto.nombre}: quedó "
                f"{producto.stock - detalle_in.cantidad}."
            )

        subtotal = precio_unitario * detalle_in.cantidad
        total_factura += subtotal

        # 2. Agregar Detalle
        db_detalle = DetalleFactura(
            factura_id=db_factura.id,
            producto_id=producto.id,
            cantidad=detalle_in.cantidad,
            precio_unitario=precio_unitario,
            subtotal=subtotal,
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
            referencia=f"Venta en Factura #{db_factura.id}",
        )
        db.add(db_kardex)

    db_factura.total = total_factura
    db_factura.saldo = total_factura  # El saldo inicial adeudado es el total
    if notas_revision:
        db_factura.requiere_revision = True
        db_factura.nota_revision = " ".join(dict.fromkeys(notas_revision))[:2000]

    factura_id = db_factura.id
    try:
        # ¡Éxito! Todo se guarda simultáneamente (Factura + Detalles + Stock + Kardex)
        db.commit()
    except IntegrityError:
        # Carrera de idempotencia en el commit (el índice único se valida al
        # final). Se descarta esta transacción y se devuelve la ganadora.
        db.rollback()
        if clave:
            existente = _buscar_factura_idempotente(db, clave, vendedor_id)
            if existente:
                return existente
        raise HTTPException(
            status_code=409,
            detail="No se pudo registrar la venta por un conflicto de concurrencia. Intenta de nuevo.",
        )

    return _factura_con_relaciones(db, factura_id)



def _buscar_pago_idempotente(
    db: Session, clave: str, factura_id: int
) -> PagoIdempotente | None:
    operacion = (
        db.query(PagoIdempotente)
        .filter(PagoIdempotente.clave == clave)
        .first()
    )
    if operacion and operacion.factura_id != factura_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "Esa clave de idempotencia ya fue usada para cobrar otra factura. "
                "No se registró ningún pago nuevo."
            ),
        )
    return operacion


def _buscar_operacion_factura_idempotente(
    db: Session, clave: str, factura_id: int, tipo: str
) -> OperacionFacturaIdempotente | None:
    operacion = (
        db.query(OperacionFacturaIdempotente)
        .filter(OperacionFacturaIdempotente.clave == clave)
        .first()
    )
    if operacion and (
        operacion.factura_id != factura_id or operacion.tipo != tipo
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Esa clave de idempotencia ya fue usada para otra operación. "
                "No se aplicó ningún cambio."
            ),
        )
    return operacion


def registrar_pagos_factura(
    db: Session,
    factura_id: int,
    pagos: list[PagoCreate],
    cajero_id: int,
    clave_idempotencia: str | None = None,
    turno_caja_id: int | None = None,
):
    """Registra uno o varios pagos (medios de pago combinados) sobre una factura."""
    if not pagos:
        raise HTTPException(status_code=400, detail="Debe registrar al menos un pago.")

    # Un reintento del navegador tras un timeout puede llegar cuando el cobro
    # ya se guardó (incluso si la caja se cerró después). En ese caso se
    # devuelve la factura tal como quedó, sin volver a cobrar.
    clave = (clave_idempotencia or "").strip() or None
    if clave and len(clave) > 64:
        raise HTTPException(
            status_code=400,
            detail="La clave de idempotencia no puede superar 64 caracteres.",
        )
    if clave:
        existente = _buscar_pago_idempotente(db, clave, factura_id)
        if existente:
            return _factura_con_relaciones(db, factura_id)

    # Los abonos por nómina no son un cobro de caja: se registran desde la
    # sección de nómina del usuario vinculado, no desde el cobro de facturas.
    if any(pago.forma_pago == FormaPago.NOMINA for pago in pagos):
        raise HTTPException(
            status_code=400,
            detail="Los abonos por nómina se registran desde la sección de nómina del usuario.",
        )

    # 1. Verificar la caja. Un cobro offline puede indicar el turno en el que
    # ocurrió; si no, se usa la caja abierta actual.
    if turno_caja_id is not None:
        caja_abierta = (
            db.query(TurnoCaja).filter(TurnoCaja.id == turno_caja_id).first()
        )
        if not caja_abierta:
            raise HTTPException(
                status_code=400, detail="Turno de caja no encontrado."
            )
        if not caja_abierta.abierta:
            raise HTTPException(
                status_code=400,
                detail=(
                    "El turno de caja ya está cerrado. Abre una caja nueva "
                    "para registrar el cobro."
                ),
            )
    else:
        caja_abierta = (
            db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
        )
        if not caja_abierta:
            raise HTTPException(status_code=400, detail="No se pueden registrar pagos. No hay una caja abierta actualmente.")

    # 2. Buscar factura (con bloqueo de fila)
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # Otra petición con la misma clave pudo terminar mientras esperábamos el
    # bloqueo de la factura. Se comprueba de nuevo antes de cobrar.
    if clave:
        existente = _buscar_pago_idempotente(db, clave, factura_id)
        if existente:
            # Soltamos el bloqueo de la factura antes de serializar.
            db.rollback()
            return _factura_con_relaciones(db, factura_id)

    if factura.estado in [EstadoFactura.PAGADA, EstadoFactura.ANULADA]:
        db.rollback()
        raise HTTPException(status_code=400, detail="La factura ya se encuentra pagada o está anulada.")

    for pago in pagos:
        if pago.valor <= 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="Cada pago debe ser mayor a 0.")
        _fecha_operacion(pago.fecha)

    total = round(sum(pago.valor for pago in pagos), 2)
    if total > factura.saldo:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"El valor total de los pagos ({total}) excede el saldo pendiente ({factura.saldo})")

    # 3. Reservar la clave antes de insertar los pagos. El índice único es la
    # última barrera si dos peticiones idénticas llegan exactamente a la vez.
    if clave:
        db.add(PagoIdempotente(clave=clave, factura_id=factura.id))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existente = _buscar_pago_idempotente(db, clave, factura_id)
            if existente:
                return _factura_con_relaciones(db, factura_id)
            raise HTTPException(
                status_code=409,
                detail="No se pudo registrar el pago por un conflicto de concurrencia. Intenta de nuevo.",
            )

    # 4. Registrar cada pago y su entrada de caja
    for pago in pagos:
        fecha_pago = _fecha_operacion(pago.fecha)
        db.add(Pago(
            factura_id=factura.id,
            cajero_id=cajero_id,
            fecha=fecha_pago,
            valor=pago.valor,
            forma_pago=pago.forma_pago
        ))
        db.add(RegistroCaja(
            turno_caja_id=caja_abierta.id,
            usuario_id=cajero_id,
            fecha=fecha_pago,
            tipo=TipoMovimientoCaja.ENTRADA,
            referencia=f"Abono a Factura #{factura.id}",
            forma_pago=pago.forma_pago,
            monto=pago.valor,
            categoria=CATEGORIA_VENTAS,
            observacion="Cobro de ventas"
        ))

    # 5. Actualizar Saldos y Estados
    factura.saldo = round(factura.saldo - total, 2)
    if factura.saldo <= 0: # Check robusto
        factura.estado = EstadoFactura.PAGADA
        factura.saldo = 0
    else:
        factura.estado = EstadoFactura.PAGADO_PARCIAL

    factura_id_guardada = factura.id
    try:
        db.commit() # Atomicidad: Pago + Flujo de Caja + Actualización de Factura
    except IntegrityError:
        db.rollback()
        if clave:
            existente = _buscar_pago_idempotente(db, clave, factura_id_guardada)
            if existente:
                return _factura_con_relaciones(db, factura_id_guardada)
        raise HTTPException(
            status_code=409,
            detail="No se pudo registrar el pago por un conflicto de concurrencia. Intenta de nuevo.",
        )

    return _factura_con_relaciones(db, factura_id_guardada)


def registrar_pago_factura(
    db: Session,
    factura_id: int,
    pago_in: PagoCreate,
    cajero_id: int,
    clave_idempotencia: str | None = None,
    turno_caja_id: int | None = None,
):
    """Compatibilidad: registra un único pago."""
    return registrar_pagos_factura(
        db,
        factura_id,
        [pago_in],
        cajero_id,
        clave_idempotencia=clave_idempotencia,
        turno_caja_id=turno_caja_id,
    )


def anular_factura(db: Session, factura_id: int, usuario_id: int, motivo: str | None = None):
    factura = db.query(Factura).filter(Factura.id == factura_id).with_for_update().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if factura.estado == EstadoFactura.ANULADA:
        db.rollback()
        raise HTTPException(status_code=400, detail="La factura ya está anulada.")

    # Una factura con abonos por nómina no se anula desde aquí: el descuento ya
    # se aplicó a la nómina del empleado y devolverlo requiere un ajuste manual.
    if any(pago.forma_pago == FormaPago.NOMINA for pago in factura.pagos):
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede anular: la factura tiene abonos por nómina. "
                "Ajusta la nómina del empleado antes de anularla."
            ),
        )

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
                    categoria=CATEGORIA_DEVOLUCION,
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
    permitir_negativo: bool = False,
) -> bool:
    """delta > 0 devuelve stock (Devolución); delta < 0 descuenta stock (Salida por Venta).

    Devuelve ``True`` si el producto quedó con stock negativo. Las operaciones
    offline pueden permitirlo: la venta ya ocurrió físicamente y se marca para
    revisión en vez de rechazarse.
    """
    if delta == 0:
        return producto.stock < 0
    if delta < 0:
        cantidad = -delta
        if producto.stock < cantidad and not permitir_negativo:
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
    return producto.stock < 0


def _recalcular_factura(db: Session, factura: Factura):
    """Recalcula total, saldo y estado tras editar los items de una factura.

    Editar cantidades NO es un evento de dinero: aquí solo se ajustan el total y
    el saldo. La caja se mueve únicamente con pagos, anulación o movimientos
    manuales, de modo que nunca aparecen ingresos/egresos fantasma. Si los pagos
    ya cubren (o superan) el nuevo total, la factura queda Pagada con saldo 0 y el
    exceso es un saldo a favor del cliente que no toca la caja.
    """
    factura.total = round(sum(d.subtotal for d in factura.detalles if not d.anulado), 2)
    pagado = round(sum(p.valor for p in factura.pagos), 2)
    saldo = round(factura.total - pagado, 2)

    if saldo <= 0:
        # Cubierta por los pagos (o pagada de más: el exceso es saldo a favor).
        factura.saldo = 0
        factura.estado = EstadoFactura.PAGADA
    elif pagado > 0:
        factura.saldo = saldo
        factura.estado = EstadoFactura.PAGADO_PARCIAL
    elif factura.estado == EstadoFactura.CREDITO:
        # Una factura ya marcada como crédito conserva ese estado al editarla.
        factura.saldo = saldo
        factura.estado = EstadoFactura.CREDITO
    else:
        factura.saldo = saldo
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
    _recalcular_factura(db, factura)

    db.commit()
    db.refresh(factura)
    return factura


def _marcar_revision(factura: Factura, nota: str) -> None:
    factura.requiere_revision = True
    actual = (factura.nota_revision or "").strip()
    if nota not in actual:
        factura.nota_revision = f"{actual} {nota}".strip()


def agregar_item_factura_offline(
    db: Session,
    factura_id: int,
    item_in: ItemFacturaCreate,
    usuario_id: int,
    clave_idempotencia: str | None,
):
    """Agrega un ítem capturado sin conexión a una factura ya existente.

    A diferencia de la edición online, conserva el precio del dispositivo y
    permite stock negativo: el servicio ya se prestó y no se puede perder la
    venta. La factura queda marcada para revisión cuando el inventario alcanza
    un valor negativo.
    """
    clave = (clave_idempotencia or "").strip()
    if not clave:
        raise HTTPException(
            status_code=400,
            detail="La operación offline necesita una clave de idempotencia.",
        )
    if len(clave) > 64:
        raise HTTPException(
            status_code=400,
            detail="La clave de idempotencia no puede superar 64 caracteres.",
        )
    if item_in.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")

    existente = _buscar_operacion_factura_idempotente(
        db, clave, factura_id, "agregar_item"
    )
    if existente:
        return _factura_con_relaciones(db, factura_id)

    factura = _bloquear_factura_mutable(db, factura_id)

    # Otra petición con la misma clave pudo terminar mientras esperábamos el
    # bloqueo de la factura. Se comprueba de nuevo antes de tocar el stock.
    existente = _buscar_operacion_factura_idempotente(
        db, clave, factura_id, "agregar_item"
    )
    if existente:
        db.rollback()
        return _factura_con_relaciones(db, factura_id)

    producto = (
        db.query(Producto)
        .filter(Producto.id == item_in.producto_id)
        .with_for_update()
        .first()
    )
    if not producto:
        db.rollback()
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    precio = producto.precio
    if item_in.precio_unitario is not None:
        if item_in.precio_unitario < 0:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="El precio cobrado del producto no puede ser negativo.",
            )
        precio = round(float(item_in.precio_unitario), 2)

    # Reservar la clave antes de modificar la factura. El índice único es la
    # última barrera si dos reintentos llegan exactamente a la vez.
    db.add(
        OperacionFacturaIdempotente(
            clave=clave,
            factura_id=factura.id,
            tipo="agregar_item",
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existente = _buscar_operacion_factura_idempotente(
            db, clave, factura_id, "agregar_item"
        )
        if existente:
            return _factura_con_relaciones(db, factura_id)
        raise HTTPException(
            status_code=409,
            detail="No se pudo agregar el ítem por un conflicto de concurrencia. Intenta de nuevo.",
        )

    detalle = next(
        (
            d
            for d in factura.detalles
            if d.producto_id == producto.id
            and not d.anulado
            and round(float(d.precio_unitario or 0), 2) == precio
        ),
        None,
    )
    if detalle:
        detalle.cantidad += item_in.cantidad
        detalle.subtotal = round(precio * detalle.cantidad, 2)
    else:
        detalle = DetalleFactura(
            producto_id=producto.id,
            cantidad=item_in.cantidad,
            precio_unitario=precio,
            subtotal=round(precio * item_in.cantidad, 2),
        )
        factura.detalles.append(detalle)

    quedo_negativo = _mover_stock(
        db,
        producto,
        -item_in.cantidad,
        usuario_id,
        f"Adición offline a Factura #{factura.id}",
        permitir_negativo=True,
    )
    if quedo_negativo:
        _marcar_revision(
            factura,
            f"Stock insuficiente de {producto.nombre}: quedó {producto.stock}.",
        )

    _recalcular_factura(db, factura)
    factura_id_guardada = factura.id

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = _buscar_operacion_factura_idempotente(
            db, clave, factura_id, "agregar_item"
        )
        if existente:
            return _factura_con_relaciones(db, factura_id)
        raise HTTPException(
            status_code=409,
            detail="No se pudo agregar el ítem por un conflicto de concurrencia. Intenta de nuevo.",
        )

    return _factura_con_relaciones(db, factura_id_guardada)


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

    _recalcular_factura(db, factura)

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
    _recalcular_factura(db, factura)

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
