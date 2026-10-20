"""Descuento de nómina por empleado y su auditoría.

Un usuario puede estar vinculado a un cliente (vínculo uno a uno). Esta capa
permite consultar la deuda a crédito del cliente vinculado y abonarla contra la
nómina del empleado: crea ``Pago`` con forma de pago ``Nómina`` y reduce el
saldo de las facturas, pero **no** genera movimientos de caja porque no es un
cobro de efectivo/banco sino una compensación.

Cada aplicación crea además un ``DescuentoNomina`` que agrupa los pagos y guarda
una foto del empleado, el cliente y el admin que lo aplicó, para que el
historial se pueda auditar aunque luego cambien los datos.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Cliente,
    DescuentoNomina,
    EstadoFactura,
    Factura,
    FormaPago,
    Pago,
    Usuario,
)


def _cliente_del_usuario(usuario: Usuario) -> Cliente:
    """Devuelve el cliente vinculado o falla si el usuario no tiene uno."""
    if not usuario.cliente_id or not usuario.cliente:
        raise HTTPException(
            status_code=400,
            detail="El usuario no tiene un cliente vinculado para descontar nómina.",
        )
    return usuario.cliente


def _cliente_actual(usuario: Usuario) -> Optional[Cliente]:
    return usuario.cliente if usuario.cliente_id else None


def _facturas_pendientes(db: Session, cliente_id: int):
    """Facturas con saldo a favor del negocio, de la más antigua a la más nueva."""
    return (
        db.query(Factura)
        .filter(
            Factura.cliente_id == cliente_id,
            Factura.estado != EstadoFactura.ANULADA,
            Factura.saldo > 0,
        )
        .order_by(Factura.fecha.asc(), Factura.id.asc())
    )


def deuda_nomina(db: Session, usuario: Usuario):
    """Deuda a crédito del cliente vinculado al usuario."""
    cliente = _cliente_del_usuario(usuario)
    facturas = _facturas_pendientes(db, cliente.id).all()
    return cliente, facturas, round(sum(f.saldo for f in facturas), 2)


def fila_descuento(descuento: DescuentoNomina) -> dict:
    """Formato de salida común para historial y reporte."""
    return {
        "id": descuento.id,
        "fecha": descuento.fecha,
        "usuario_id": descuento.usuario_id,
        "usuario_nombre": descuento.usuario_nombre,
        "cliente_id": descuento.cliente_id,
        "cliente_nombre": descuento.cliente_nombre,
        "monto": descuento.monto,
        "saldo_pendiente": descuento.saldo_pendiente,
        "facturas_afectadas": descuento.facturas_afectadas,
        "registrado_por": descuento.registrado_por_nombre,
        "nota": descuento.nota,
    }


def fila_historial(descuento: DescuentoNomina) -> dict:
    """Evento + facturas concretas que cubrió (para el detalle del historial)."""
    data = fila_descuento(descuento)
    data["facturas"] = [
        {
            "factura_id": pago.factura_id,
            "fecha": pago.factura.fecha,
            "total": pago.factura.total,
            "abono": pago.valor,
            "saldo_actual": pago.factura.saldo,
        }
        for pago in descuento.pagos
        if pago.factura is not None
    ]
    return data


def aplicar_descuento_nomina(
    db: Session,
    usuario: Usuario,
    monto: Optional[float],
    registrado_por: Usuario,
    nota: Optional[str] = None,
) -> DescuentoNomina:
    """Aplica un abono de nómina (total o parcial) a la deuda del empleado.

    Reparte el monto entre las facturas más antiguas primero. Si ``monto`` es
    ``None`` se abona toda la deuda pendiente. No requiere caja abierta ni
    genera movimientos de caja. Devuelve el evento de auditoría creado.
    """
    cliente = _cliente_del_usuario(usuario)

    facturas = _facturas_pendientes(db, cliente.id).with_for_update().all()
    saldo_total = round(sum(f.saldo for f in facturas), 2)
    if saldo_total <= 0:
        raise HTTPException(
            status_code=400,
            detail="El empleado no tiene deuda pendiente por descontar.",
        )

    if monto is None:
        a_aplicar = saldo_total
    else:
        a_aplicar = round(monto, 2)
        if a_aplicar <= 0:
            raise HTTPException(
                status_code=400, detail="El monto a descontar debe ser mayor a 0."
            )
        if a_aplicar > saldo_total:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El monto a descontar ({a_aplicar}) supera la deuda "
                    f"pendiente ({saldo_total})."
                ),
            )

    # Cabecera de auditoría: foto de los nombres en el momento del descuento.
    descuento = DescuentoNomina(
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre,
        cliente_id=cliente.id,
        cliente_nombre=cliente.nombre,
        registrado_por_id=registrado_por.id,
        registrado_por_nombre=registrado_por.nombre,
        monto=a_aplicar,
        saldo_pendiente=round(saldo_total - a_aplicar, 2),
        facturas_afectadas=0,
        nota=(nota or "").strip() or None,
    )
    db.add(descuento)
    db.flush()

    restante = a_aplicar
    for factura in facturas:
        if restante <= 0:
            break
        abono = round(min(factura.saldo, restante), 2)
        db.add(
            Pago(
                factura_id=factura.id,
                cajero_id=registrado_por.id,
                valor=abono,
                forma_pago=FormaPago.NOMINA,
                descuento_nomina_id=descuento.id,
            )
        )
        factura.saldo = round(factura.saldo - abono, 2)
        if factura.saldo <= 0:
            factura.saldo = 0
            factura.estado = EstadoFactura.PAGADA
        else:
            factura.estado = EstadoFactura.PAGADO_PARCIAL
        descuento.facturas_afectadas += 1
        restante = round(restante - abono, 2)

    db.commit()
    db.refresh(descuento)
    return descuento


def historial_nomina(
    db: Session, usuario: Usuario, limite: int = 100
) -> tuple[Optional[Cliente], float, list[DescuentoNomina], int, float]:
    """Historial de descuentos del empleado y su deuda actual.

    Funciona aunque el usuario ya no tenga cliente vinculado: las filas del
    historial conservan el nombre del cliente de ese momento.

    Devuelve ``(cliente_actual, saldo_actual, ultimos_eventos, total_eventos,
    monto_total)``. El total se calcula sobre todo el historial, no solo sobre
    la página de eventos que se devuelve.
    """
    cliente = _cliente_actual(usuario)
    facturas = (
        _facturas_pendientes(db, cliente.id).all() if cliente is not None else []
    )
    saldo = round(sum(f.saldo for f in facturas), 2)

    base = db.query(DescuentoNomina).filter(
        DescuentoNomina.usuario_id == usuario.id
    )
    total, monto_total = base.with_entities(
        func.count(DescuentoNomina.id),
        func.coalesce(func.sum(DescuentoNomina.monto), 0.0),
    ).one()
    filas = (
        base.options(
            selectinload(DescuentoNomina.pagos).selectinload(Pago.factura)
        )
        .order_by(DescuentoNomina.fecha.desc(), DescuentoNomina.id.desc())
        .limit(max(1, min(limite, 500)))
        .all()
    )
    return cliente, saldo, filas, int(total), float(monto_total)
