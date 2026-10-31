from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import (
    Usuario,
    Factura,
    Producto,
    Cliente,
    TurnoCaja,
    EstadoFactura,
)
from app.crud import crud_caja
from app.api.deps import require_permiso
from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.services import bolsillos as bolsillos_service
from app.schemas.dashboard import (
    DashboardResumen,
    DashboardKpis,
    VentaDia,
    VentaMes,
    ProductoBajoStock,
    CajaResumen,
)

router = APIRouter()

UMBRAL_BAJO_STOCK = 10


def _meses_ultimos(ahora: datetime, cantidad: int = 12) -> list[tuple[int, int]]:
    """Lista de (año, mes) desde el más antiguo hasta el actual."""
    anio, mes = ahora.year, ahora.month
    meses: list[tuple[int, int]] = []
    for _ in range(cantidad):
        meses.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return list(reversed(meses))


def _fecha_bogota(fecha: datetime) -> datetime:
    """Normaliza una fecha para agruparla en hora de Colombia.

    PostgreSQL devuelve la fecha con zona; SQLite (pruebas) la guarda ya en
    hora local sin zona. En ambos casos el resultado es la hora de Colombia.
    """
    if fecha.tzinfo is None:
        return fecha
    return fecha.astimezone(BOGOTA_TZ)


def _ventas_agrupadas(
    db: Session, desde: datetime, hasta: datetime
) -> list[tuple[datetime, float]]:
    """Facturas no anuladas del rango, con su fecha y total."""
    return (
        db.query(Factura.fecha, Factura.total)
        .filter(
            Factura.fecha >= desde,
            Factura.fecha < hasta,
            Factura.estado != EstadoFactura.ANULADA,
        )
        .all()
    )


@router.get("/", response_model=DashboardResumen)
def resumen_dashboard(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("dashboard.ver")),
):
    ahora = get_colombia_time()
    hoy = ahora.date()
    manana = datetime.combine(hoy + timedelta(days=1), time.min, tzinfo=BOGOTA_TZ)
    inicio_7d = datetime.combine(hoy - timedelta(days=6), time.min, tzinfo=BOGOTA_TZ)

    # --- Ventas de los últimos 7 días (agrupadas por día en hora de Colombia) ---
    por_dia: dict[str, dict[str, float]] = {}
    for fecha, total in _ventas_agrupadas(db, inicio_7d, manana):
        clave = _fecha_bogota(fecha).date().isoformat()
        acumulado = por_dia.setdefault(clave, {"total": 0.0, "cantidad": 0})
        acumulado["total"] += float(total or 0.0)
        acumulado["cantidad"] += 1

    ventas_7d: list[VentaDia] = []
    for i in range(7):
        d = hoy - timedelta(days=6 - i)
        acumulado = por_dia.get(d.isoformat(), {"total": 0.0, "cantidad": 0})
        ventas_7d.append(
            VentaDia(
                fecha=d.isoformat(),
                total=round(float(acumulado["total"]), 2),
                cantidad=int(acumulado["cantidad"]),
            )
        )
    ventas_hoy = ventas_7d[-1]
    ventas_7d_total = round(sum(v.total for v in ventas_7d), 2)

    # --- Ventas mes a mes (últimos 12 meses, incluido el actual) ---
    meses = _meses_ultimos(ahora)
    anio_inicial, mes_inicial = meses[0]
    inicio_12m = datetime.combine(
        date(anio_inicial, mes_inicial, 1), time.min, tzinfo=BOGOTA_TZ
    )
    por_mes: dict[str, dict[str, float]] = {}
    for fecha, total in _ventas_agrupadas(db, inicio_12m, manana):
        f = _fecha_bogota(fecha)
        clave = f"{f.year:04d}-{f.month:02d}"
        acumulado = por_mes.setdefault(clave, {"total": 0.0, "cantidad": 0})
        acumulado["total"] += float(total or 0.0)
        acumulado["cantidad"] += 1

    ventas_12m: list[VentaMes] = []
    for anio, mes in meses:
        clave = f"{anio:04d}-{mes:02d}"
        acumulado = por_mes.get(clave, {"total": 0.0, "cantidad": 0})
        ventas_12m.append(
            VentaMes(
                mes=clave,
                total=round(float(acumulado["total"]), 2),
                cantidad=int(acumulado["cantidad"]),
            )
        )
    ventas_mes = ventas_12m[-1]

    # --- Cartera (saldo por cobrar) y facturas pendientes ---
    cartera_total = float(
        db.query(func.coalesce(func.sum(Factura.saldo), 0.0))
        .filter(Factura.estado != EstadoFactura.ANULADA, Factura.saldo > 0)
        .scalar()
    )
    facturas_pendientes = int(
        db.query(func.count(Factura.id))
        .filter(
            Factura.estado.in_([EstadoFactura.ABIERTA, EstadoFactura.PAGADO_PARCIAL]),
            Factura.saldo > 0,
        )
        .scalar()
    )
    facturas_credito = int(
        db.query(func.count(Factura.id))
        .filter(Factura.estado == EstadoFactura.CREDITO, Factura.saldo > 0)
        .scalar()
    )

    # --- Facturas por estado ---
    claves = {
        EstadoFactura.ABIERTA: "Abierta",
        EstadoFactura.PAGADO_PARCIAL: "Pagado Parcial",
        EstadoFactura.PAGADA: "Pagada",
        EstadoFactura.CREDITO: "Crédito",
        EstadoFactura.ANULADA: "Anulada",
    }
    facturas_por_estado = {nombre: 0 for nombre in claves.values()}
    for estado, cantidad in db.query(Factura.estado, func.count(Factura.id)).group_by(Factura.estado).all():
        nombre = claves.get(estado, str(estado))
        facturas_por_estado[nombre] = int(cantidad)

    # --- Productos con bajo stock ---
    bajos = (
        db.query(Producto)
        .filter(Producto.stock <= UMBRAL_BAJO_STOCK)
        .order_by(Producto.stock.asc(), Producto.nombre.asc())
        .all()
    )
    productos_bajo_stock = [
        ProductoBajoStock(id=p.id, codigo=p.codigo, nombre=p.nombre, stock=p.stock)
        for p in bajos
    ]

    # --- Caja y bolsillos de gastos vitales ---
    turno = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
    saldos_caja = crud_caja.saldos_actuales(db)
    reservado = bolsillos_service.total_reservado(db)
    # Solo el reservado que salió de caja/banco reduce el disponible; el saldo
    # inicial de un bolsillo ya estaba apartado y no se descuenta.
    disponible = bolsillos_service.caja_disponible(db)

    if turno:
        entradas, salidas = crud_caja.resumen_movimientos(db, turno.id)
        caja = CajaResumen(
            abierta=True,
            turno_id=turno.id,
            saldo_inicial_efectivo=turno.saldo_inicial_efectivo,
            saldo_inicial_banco=turno.saldo_inicial_banco,
            entradas_efectivo=entradas["efectivo"],
            entradas_banco=entradas["banco"],
            salidas_efectivo=salidas["efectivo"],
            salidas_banco=salidas["banco"],
            esperado_efectivo=(
                turno.saldo_inicial_efectivo + entradas["efectivo"] - salidas["efectivo"]
            ),
            esperado_banco=(
                turno.saldo_inicial_banco + entradas["banco"] - salidas["banco"]
            ),
            reservado=reservado,
            disponible=disponible,
        )
    else:
        # Sin turno abierto se muestra el saldo del último cierre para que el
        # bolsillo y la liquidez disponible sigan siendo visibles.
        caja = CajaResumen(
            abierta=False,
            turno_id=saldos_caja["turno_id"],
            esperado_efectivo=round(float(saldos_caja["efectivo"]), 2),
            esperado_banco=round(float(saldos_caja["banco"]), 2),
            reservado=reservado,
            disponible=disponible,
        )

    total_clientes = int(db.query(func.count(Cliente.id)).scalar())
    total_productos = int(db.query(func.count(Producto.id)).scalar())

    return DashboardResumen(
        kpis=DashboardKpis(
            ventas_hoy_total=ventas_hoy.total,
            ventas_hoy_cantidad=ventas_hoy.cantidad,
            ventas_7d_total=ventas_7d_total,
            ventas_mes_total=ventas_mes.total,
            ventas_mes_cantidad=ventas_mes.cantidad,
            cartera_total=cartera_total,
            facturas_pendientes=facturas_pendientes,
            facturas_credito=facturas_credito,
        ),
        ventas_ultimos_7_dias=ventas_7d,
        ventas_ultimos_12_meses=ventas_12m,
        productos_bajo_stock=productos_bajo_stock,
        facturas_por_estado=facturas_por_estado,
        caja=caja,
        total_clientes=total_clientes,
        total_productos=total_productos,
    )
