from datetime import datetime, time, timedelta
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
    RegistroCaja,
    EstadoFactura,
    TipoMovimientoCaja,
)
from app.api.deps import get_current_active_user
from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.schemas.dashboard import (
    DashboardResumen,
    DashboardKpis,
    VentaDia,
    ProductoBajoStock,
    CajaResumen,
)

router = APIRouter()

UMBRAL_BAJO_STOCK = 10


@router.get("/", response_model=DashboardResumen)
def resumen_dashboard(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    ahora = get_colombia_time()
    hoy = ahora.date()
    inicio_7d = datetime.combine(hoy - timedelta(days=6), time.min, tzinfo=BOGOTA_TZ)

    # --- Ventas de los últimos 7 días (agrupadas por día en hora de Colombia) ---
    dia_expr = func.date_trunc("day", func.timezone("America/Bogota", Factura.fecha))
    filas = (
        db.query(
            dia_expr.label("dia"),
            func.count(Factura.id).label("cantidad"),
            func.coalesce(func.sum(Factura.total), 0.0).label("total"),
        )
        .filter(Factura.fecha >= inicio_7d, Factura.estado != EstadoFactura.ANULADA)
        .group_by(dia_expr)
        .all()
    )
    por_dia = {fila.dia.date().isoformat(): fila for fila in filas}

    ventas_7d: list[VentaDia] = []
    for i in range(7):
        d = hoy - timedelta(days=6 - i)
        fila = por_dia.get(d.isoformat())
        ventas_7d.append(
            VentaDia(
                fecha=d.isoformat(),
                total=float(fila.total) if fila else 0.0,
                cantidad=int(fila.cantidad) if fila else 0,
            )
        )
    ventas_hoy = ventas_7d[-1]
    ventas_7d_total = sum(v.total for v in ventas_7d)

    # --- Cartera (saldo por cobrar) y facturas pendientes ---
    cartera_total = float(
        db.query(func.coalesce(func.sum(Factura.saldo), 0.0))
        .filter(Factura.estado != EstadoFactura.ANULADA, Factura.saldo > 0)
        .scalar()
    )
    facturas_pendientes = int(
        db.query(func.count(Factura.id))
        .filter(
            Factura.estado.in_([EstadoFactura.PENDIENTE, EstadoFactura.PAGADO_PARCIAL]),
            Factura.saldo > 0,
        )
        .scalar()
    )

    # --- Facturas por estado ---
    claves = {
        EstadoFactura.PENDIENTE: "Pendiente",
        EstadoFactura.PAGADO_PARCIAL: "Pagado Parcial",
        EstadoFactura.PAGADA: "Pagada",
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
        .limit(10)
        .all()
    )
    productos_bajo_stock = [
        ProductoBajoStock(id=p.id, codigo=p.codigo, nombre=p.nombre, stock=p.stock)
        for p in bajos
    ]

    # --- Caja abierta ---
    turno = db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()
    if turno:
        entradas = float(
            db.query(func.coalesce(func.sum(RegistroCaja.monto), 0.0))
            .filter(
                RegistroCaja.turno_caja_id == turno.id,
                RegistroCaja.tipo == TipoMovimientoCaja.ENTRADA,
            )
            .scalar()
        )
        salidas = float(
            db.query(func.coalesce(func.sum(RegistroCaja.monto), 0.0))
            .filter(
                RegistroCaja.turno_caja_id == turno.id,
                RegistroCaja.tipo == TipoMovimientoCaja.SALIDA,
            )
            .scalar()
        )
        caja = CajaResumen(
            abierta=True,
            turno_id=turno.id,
            saldo_inicial=turno.saldo_inicial,
            entradas=entradas,
            salidas=salidas,
            esperado=turno.saldo_inicial + entradas - salidas,
        )
    else:
        caja = CajaResumen(abierta=False)

    total_clientes = int(db.query(func.count(Cliente.id)).scalar())
    total_productos = int(db.query(func.count(Producto.id)).scalar())

    return DashboardResumen(
        kpis=DashboardKpis(
            ventas_hoy_total=ventas_hoy.total,
            ventas_hoy_cantidad=ventas_hoy.cantidad,
            ventas_7d_total=ventas_7d_total,
            cartera_total=cartera_total,
            facturas_pendientes=facturas_pendientes,
        ),
        ventas_ultimos_7_dias=ventas_7d,
        productos_bajo_stock=productos_bajo_stock,
        facturas_por_estado=facturas_por_estado,
        caja=caja,
        total_clientes=total_clientes,
        total_productos=total_productos,
    )
