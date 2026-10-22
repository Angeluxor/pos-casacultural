"""Cálculo del balance general operativo.

Supuestos del cálculo:

- **Caja/banco**: saldo esperado del turno abierto; si no hay turno abierto, el
  saldo real del último cierre.
- **Bolsillos**: apartan una parte de efectivo/banco para gastos vitales. El
  dinero sigue sumando al activo (no se cuenta dos veces) pero se resta del
  disponible para operación. Los aportes/retiros no son ingresos ni gastos.
- **Cartera**: saldo pendiente de las facturas no anuladas.
- **Inventario**: stock por costo promedio de las compras. Si un producto nunca
  tuvo costo, se valoriza a precio de venta y se marca como respaldo.
- **Cuentas por pagar**: compras a crédito aún no pagadas, sin importar si se
  registraron desde la caja o desde el balance general.
- **Ingresos en balance general**: no mueven caja. Los de efectivo o
  transferencia se consideran pagados por fuera del POS y su contrapartida
  queda en el patrimonio residual; los de crédito son cuentas por pagar.
- **Patrimonio**: activos menos pasivos (residual). No se llevan aportes ni
  retiros de capital.
- **Resultados**: ventas no anuladas del período menos costo de ventas y gastos.
  El costo de ventas usa el costo promedio actual; los gastos son las salidas
  de caja que no corresponden a compras de inventario, pagos de esas compras
  ni devoluciones por anulación, más los ítems "Otros" de los ingresos (que no
  son inventario). Las facturas anuladas no se reconocen como venta y su
  devolución tampoco como gasto.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func, not_
from sqlalchemy.orm import Session, joinedload

from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.crud import crud_caja
from app.services import bolsillos
from app.services.costos import CostoVigente, costos_vigentes
from app.db.models import (
    DetalleFactura,
    EstadoFactura,
    Factura,
    FormaPagoIngreso,
    IngresoInventario,
    IngresoInventarioItem,
    Producto,
    RegistroCaja,
    TipoItemIngreso,
    TipoMovimientoCaja,
)
from app.schemas.balance import (
    BalanceActivos,
    BalanceGeneral,
    BalancePasivos,
    BalancePatrimonio,
    CuentaPorPagar,
    FilaInventarioBalance,
    ResultadosPeriodo,
    SaldosCaja,
)


def _rango_desde(desde: Optional[str]) -> Optional[datetime]:
    if not desde:
        return None
    try:
        return datetime.combine(date.fromisoformat(desde), time.min, tzinfo=BOGOTA_TZ)
    except ValueError:
        return None


def _rango_hasta(hasta: Optional[str]) -> Optional[datetime]:
    if not hasta:
        return None
    try:
        h = date.fromisoformat(hasta)
        return datetime.combine(h + timedelta(days=1), time.min, tzinfo=BOGOTA_TZ)
    except ValueError:
        return None


def _costos_promedio(db: Session) -> dict[int, CostoVigente]:
    """Costo vigente por producto (compra, manual o receta)."""
    return costos_vigentes(db)


def _inventario(
    db: Session, costos: dict[int, CostoVigente]
) -> tuple[
    list[FilaInventarioBalance],
    int,
    float,
    dict[int, Producto],
]:
    productos = db.query(Producto).all()
    por_id = {p.id: p for p in productos}
    items: list[FilaInventarioBalance] = []
    sin_costo = 0
    valor_precio_venta = 0.0

    for producto in productos:
        stock = int(producto.stock or 0)
        if stock <= 0:
            continue
        info = costos.get(producto.id)
        if info is not None:
            costo = round(info.costo, 2)
            origen = info.origen
        else:
            costo = round(float(producto.precio or 0.0), 2)
            origen = "Precio de venta"
            sin_costo += 1
            valor_precio_venta += stock * costo
        valor = round(stock * costo, 2)
        items.append(
            FilaInventarioBalance(
                producto_id=producto.id,
                codigo=producto.codigo,
                nombre=producto.nombre,
                stock=stock,
                costo_unitario=costo,
                valor=valor,
                origen=origen,
            )
        )

    items.sort(key=lambda i: (-i.valor, i.nombre.lower()))
    return items, sin_costo, round(valor_precio_venta, 2), por_id


def _resultados(
    db: Session,
    desde: Optional[str],
    hasta: Optional[str],
    costos: dict[int, CostoVigente],
    productos: dict[int, Producto],
) -> ResultadosPeriodo:
    inicio = _rango_desde(desde)
    fin = _rango_hasta(hasta)

    cond_factura = [Factura.estado != EstadoFactura.ANULADA]
    if inicio:
        cond_factura.append(Factura.fecha >= inicio)
    if fin:
        cond_factura.append(Factura.fecha < fin)

    ventas_netas = float(
        db.query(func.coalesce(func.sum(Factura.total), 0.0))
        .filter(*cond_factura)
        .scalar()
    )
    facturas = int(
        db.query(func.count(Factura.id)).filter(*cond_factura).scalar() or 0
    )

    filas_costo = (
        db.query(
            DetalleFactura.producto_id,
            func.sum(DetalleFactura.cantidad),
        )
        .join(Factura, Factura.id == DetalleFactura.factura_id)
        .filter(
            DetalleFactura.anulado == False,  # noqa: E712
            *cond_factura,
        )
        .group_by(DetalleFactura.producto_id)
        .all()
    )
    costo_ventas = 0.0
    vendidos_sin_costo: set[int] = set()
    for producto_id, cantidad in filas_costo:
        producto = productos.get(int(producto_id))
        if not producto:
            continue
        info = costos.get(int(producto_id))
        if info is not None:
            costo_unitario = info.costo
        else:
            costo_unitario = float(producto.precio or 0.0)
            vendidos_sin_costo.add(int(producto_id))
        costo_ventas += float(cantidad or 0) * costo_unitario

    cond_caja = [RegistroCaja.tipo == TipoMovimientoCaja.SALIDA]
    if inicio:
        cond_caja.append(RegistroCaja.fecha >= inicio)
    if fin:
        cond_caja.append(RegistroCaja.fecha < fin)
    gastos_caja = float(
        db.query(func.coalesce(func.sum(RegistroCaja.monto), 0.0))
        .filter(*cond_caja)
        .filter(
            not_(
                func.coalesce(RegistroCaja.referencia, "").like("Ingreso #%")
            ),
            not_(
                func.coalesce(RegistroCaja.referencia, "").like(
                    "Pago ingreso #%"
                )
            ),
            # La devolución de una factura anulada no es un gasto: la venta
            # tampoco se reconoce en los ingresos del período.
            not_(
                func.coalesce(RegistroCaja.referencia, "").like(
                    "Anulación Factura #%"
                )
            ),
        )
        .scalar()
    )

    cond_otros = [
        IngresoInventarioItem.tipo == TipoItemIngreso.OTROS,
        IngresoInventario.forma_pago != FormaPagoIngreso.DONACION,
        IngresoInventario.anulada == False,  # noqa: E712
    ]
    if inicio:
        cond_otros.append(IngresoInventario.fecha >= inicio)
    if fin:
        cond_otros.append(IngresoInventario.fecha < fin)
    gastos_otros = float(
        db.query(func.coalesce(func.sum(IngresoInventarioItem.valor), 0.0))
        .join(
            IngresoInventario,
            IngresoInventario.id == IngresoInventarioItem.ingreso_id,
        )
        .filter(*cond_otros)
        .scalar()
    )

    ventas_netas = round(ventas_netas, 2)
    costo_ventas = round(costo_ventas, 2)
    gastos_caja = round(gastos_caja, 2)
    gastos_otros = round(gastos_otros, 2)
    gastos = round(gastos_caja + gastos_otros, 2)
    utilidad_bruta = round(ventas_netas - costo_ventas, 2)
    utilidad = round(utilidad_bruta - gastos, 2)
    margen = round((utilidad / ventas_netas) * 100, 2) if ventas_netas else 0.0

    return ResultadosPeriodo(
        desde=desde,
        hasta=hasta,
        ventas_netas=ventas_netas,
        costo_ventas=costo_ventas,
        utilidad_bruta=utilidad_bruta,
        gastos=gastos,
        gastos_caja=gastos_caja,
        gastos_otros=gastos_otros,
        utilidad=utilidad,
        margen=margen,
        facturas=facturas,
        productos_vendidos_sin_costo=len(vendidos_sin_costo),
    )


def _cuentas_por_pagar(
    db: Session,
) -> tuple[list[CuentaPorPagar], float]:
    ingresos = (
        db.query(IngresoInventario)
        .options(joinedload(IngresoInventario.proveedor_rel))
        .filter(
            IngresoInventario.forma_pago == FormaPagoIngreso.CREDITO,
            IngresoInventario.pagado == False,  # noqa: E712
            IngresoInventario.anulada == False,  # noqa: E712
        )
        .order_by(IngresoInventario.fecha.asc(), IngresoInventario.id.asc())
        .all()
    )
    items = [
        CuentaPorPagar(
            ingreso_id=i.id,
            fecha=i.fecha,
            proveedor=i.proveedor,
            total=round(float(i.total or 0.0), 2),
            estado_ingreso=(
                i.estado.value if hasattr(i.estado, "value") else str(i.estado)
            ),
            forma_pago_pago=(
                i.forma_pago_pago.value
                if i.forma_pago_pago is not None
                else None
            ),
            fecha_pago=i.fecha_pago,
        )
        for i in ingresos
    ]
    total = round(sum(i.total for i in items), 2)
    return items, total


def calcular_balance(
    db: Session, desde: Optional[str] = None, hasta: Optional[str] = None
) -> BalanceGeneral:
    caja = crud_caja.saldos_actuales(db)
    total_reservado, items_bolsillos = bolsillos.resumen_bolsillos(db)
    disponible = round(
        float(caja["efectivo"]) + float(caja["banco"]) - total_reservado, 2
    )
    saldos_caja = SaldosCaja(
        **caja, reservado=total_reservado, disponible=disponible
    )

    costos = _costos_promedio(db)
    inventario, sin_costo, valor_precio_venta, productos = _inventario(db, costos)
    resultados = _resultados(db, desde, hasta, costos, productos)
    cuentas, total_pasivos = _cuentas_por_pagar(db)

    cartera = float(
        db.query(func.coalesce(func.sum(Factura.saldo), 0.0))
        .filter(
            Factura.estado != EstadoFactura.ANULADA,
            Factura.saldo > 0,
        )
        .scalar()
    )
    cartera = round(cartera, 2)

    efectivo = round(float(saldos_caja.efectivo), 2)
    banco = round(float(saldos_caja.banco), 2)
    inventario_total = round(sum(i.valor for i in inventario), 2)
    total_activos = round(
        efectivo + banco + inventario_total + cartera, 2
    )
    activos = BalanceActivos(
        efectivo=efectivo,
        banco=banco,
        reservado=total_reservado,
        disponible=disponible,
        inventario=inventario_total,
        cartera=cartera,
        total=total_activos,
    )
    pasivos = BalancePasivos(
        cuentas_por_pagar=total_pasivos,
        total=total_pasivos,
    )
    patrimonio = BalancePatrimonio(
        total=round(total_activos - total_pasivos, 2)
    )

    ahora = get_colombia_time()
    return BalanceGeneral(
        generado=ahora,
        fecha_corte=ahora,
        caja=saldos_caja,
        activos=activos,
        pasivos=pasivos,
        patrimonio=patrimonio,
        resultados=resultados,
        inventario=inventario,
        cuentas_por_pagar=cuentas,
        bolsillos=items_bolsillos,
        total_reservado=total_reservado,
        productos_sin_costo=sin_costo,
        valor_inventario_precio_venta=valor_precio_venta,
        compras_credito_pendientes=len(cuentas),
    )
