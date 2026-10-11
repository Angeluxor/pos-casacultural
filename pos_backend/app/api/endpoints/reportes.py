from datetime import date, datetime, time, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import (
    Cliente,
    DetalleFactura,
    EstadoFactura,
    Factura,
    Pago,
    Producto,
    RegistroCaja,
    TurnoCaja,
    TipoMovimientoCaja,
    Usuario,
)
from app.api.deps import require_admin
from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.schemas.reportes import (
    FilaCartera,
    FilaCierreCaja,
    FilaInventario,
    FilaTopProducto,
    FilaVentaDetalle,
    FormaPagoMonto,
    ReporteCaja,
    ReporteCartera,
    ReporteInventario,
    ReporteTopProductos,
    ReporteVentas,
    VentaPorDia,
)
from app.services.reportes_export import excel_reporte, pdf_reporte

router = APIRouter(dependencies=[Depends(require_admin)])

LIMITE_TOP = 50


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


def _filtro_periodo(desde: Optional[str], hasta: Optional[str]):
    """Filtro combinado de rango sobre Factura.fecha."""
    cond = []
    inicio = _rango_desde(desde)
    fin = _rango_hasta(hasta)
    if inicio:
        cond.append(Factura.fecha >= inicio)
    if fin:
        cond.append(Factura.fecha < fin)
    return cond


# ---------------------------------------------------------------- Ventas


def _datos_ventas(db: Session, desde: str | None, hasta: str | None) -> ReporteVentas:
    cond = _filtro_periodo(desde, hasta)

    facturas = int(db.query(func.count(Factura.id)).filter(*cond).scalar() or 0)
    facturas_anuladas = int(
        db.query(func.count(Factura.id))
        .filter(*cond, Factura.estado == EstadoFactura.ANULADA)
        .scalar()
        or 0
    )
    total_vendido = float(
        db.query(func.coalesce(func.sum(Factura.total), 0.0))
        .filter(*cond, Factura.estado != EstadoFactura.ANULADA)
        .scalar()
    )
    total_anulado = float(
        db.query(func.coalesce(func.sum(Factura.total), 0.0))
        .filter(*cond, Factura.estado == EstadoFactura.ANULADA)
        .scalar()
    )

    dia_expr = func.date_trunc("day", func.timezone("America/Bogota", Factura.fecha))
    filas_dia = (
        db.query(
            dia_expr.label("dia"),
            func.count(Factura.id).label("facturas"),
            func.coalesce(func.sum(Factura.total), 0.0).label("total"),
            func.sum(case((Factura.estado == EstadoFactura.ANULADA, 1), else_=0)).label("anuladas"),
            func.sum(
                case(
                    (Factura.estado == EstadoFactura.ANULADA, Factura.total),
                    else_=0.0,
                )
            ).label("total_anulado"),
        )
        .filter(*cond)
        .group_by(dia_expr)
        .order_by(dia_expr.asc())
        .all()
    )
    por_dia = [
        VentaPorDia(
            fecha=f.dia,
            facturas=int(f.facturas),
            anuladas=int(f.anuladas or 0),
            total=float(f.total),
            total_anulado=float(f.total_anulado or 0.0),
        )
        for f in filas_dia
    ]

    filas_fp = (
        db.query(Pago.forma_pago, func.coalesce(func.sum(Pago.valor), 0.0))
        .join(Factura, Pago.factura_id == Factura.id)
        .filter(Factura.estado != EstadoFactura.ANULADA)
        .filter(*cond)
        .group_by(Pago.forma_pago)
        .order_by(func.sum(Pago.valor).desc())
        .all()
    )
    por_forma_pago = [
        FormaPagoMonto(forma_pago=fp.value if hasattr(fp, "value") else str(fp), monto=float(monto))
        for fp, monto in filas_fp
    ]

    filas_detalle = (
        db.query(Factura, Cliente.nombre.label("cliente"), Usuario.nombre.label("vendedor"))
        .join(Cliente, Factura.cliente_id == Cliente.id, isouter=True)
        .join(Usuario, Factura.vendedor_id == Usuario.id)
        .filter(*cond)
        .order_by(Factura.fecha.asc(), Factura.id.asc())
        .all()
    )
    detalle = [
        FilaVentaDetalle(
            id=f.id,
            fecha=f.fecha,
            cliente=cliente,
            vendedor=vendedor or "",
            estado=f.estado.value if hasattr(f.estado, "value") else str(f.estado),
            total=float(f.total),
            saldo=float(f.saldo),
        )
        for f, cliente, vendedor in filas_detalle
    ]

    return ReporteVentas(
        desde=desde,
        hasta=hasta,
        generado=get_colombia_time(),
        facturas=facturas,
        facturas_anuladas=facturas_anuladas,
        total_vendido=total_vendido,
        total_anulado=total_anulado,
        neto=total_vendido,
        por_dia=por_dia,
        por_forma_pago=por_forma_pago,
        detalle=detalle,
    )


HEADER_VENTAS = ["Fecha", "# Factura", "Cliente", "Vendedor", "Estado", "Total", "Saldo"]


def _filas_ventas(reporte: ReporteVentas) -> list[list]:
    filas = []
    for d in reporte.detalle:
        filas.append(
            [d.fecha, d.id, d.cliente or "", d.vendedor, d.estado, d.total, d.saldo]
        )
    return filas


def _resumen_ventas(reporte: ReporteVentas) -> list[tuple[str, float | int]]:
    return [
        ("Ventas (facturas)", reporte.facturas - reporte.facturas_anuladas),
        ("Facturas anuladas", reporte.facturas_anuladas),
        ("Total vendido", reporte.total_vendido),
        ("Total anulado", reporte.total_anulado),
        ("Neto", reporte.neto),
    ]


# ---------------------------------------------------------------- Top productos


def _datos_top(
    db: Session, desde: str | None, hasta: str | None, limite: int
) -> ReporteTopProductos:
    cond = _filtro_periodo(desde, hasta)
    query = (
        db.query(
            Producto.codigo.label("codigo"),
            Producto.nombre.label("nombre"),
            func.sum(DetalleFactura.cantidad).label("cantidad"),
            func.coalesce(func.sum(DetalleFactura.subtotal), 0.0).label("total"),
        )
        .join(DetalleFactura, DetalleFactura.producto_id == Producto.id)
        .join(Factura, Factura.id == DetalleFactura.factura_id)
        .filter(
            DetalleFactura.anulado == False,  # noqa: E712
            Factura.estado != EstadoFactura.ANULADA,
        )
        .filter(*cond)
        .group_by(Producto.id, Producto.codigo, Producto.nombre)
        .order_by(func.sum(DetalleFactura.cantidad).desc(), Producto.nombre.asc())
        .limit(limite)
    )
    filas = query.all()

    items = [
        FilaTopProducto(
            codigo=codigo,
            nombre=nombre,
            cantidad=int(cantidad),
            total=float(total),
            precio_promedio=float(total / cantidad) if cantidad else 0.0,
        )
        for codigo, nombre, cantidad, total in filas
    ]
    return ReporteTopProductos(
        desde=desde,
        hasta=hasta,
        generado=get_colombia_time(),
        renglones=len(items),
        cantidad_total=sum(i.cantidad for i in items),
        total_vendido=sum(i.total for i in items),
        items=items,
    )


HEADER_TOP = ["Código", "Producto", "Cantidad", "Precio promedio", "Total vendido"]


def _filas_top(reporte: ReporteTopProductos) -> list[list]:
    return [
        [i.codigo, i.nombre, i.cantidad, i.precio_promedio, i.total]
        for i in reporte.items
    ]


def _resumen_top(reporte: ReporteTopProductos) -> list[tuple[str, float | int]]:
    return [
        ("Productos listados", reporte.renglones),
        ("Unidades vendidas", reporte.cantidad_total),
        ("Total vendido", reporte.total_vendido),
    ]


# ---------------------------------------------------------------- Cartera


def _datos_cartera(db: Session) -> ReporteCartera:
    filas = (
        db.query(
            Cliente.id,
            Cliente.nombre,
            Cliente.documento,
            func.count(Factura.id).label("facturas"),
            func.coalesce(func.sum(Factura.total), 0.0).label("total"),
            func.coalesce(func.sum(Factura.saldo), 0.0).label("saldo"),
        )
        .join(Factura, Factura.cliente_id == Cliente.id)
        .filter(Factura.estado != EstadoFactura.ANULADA, Factura.saldo > 0)
        .group_by(Cliente.id, Cliente.nombre, Cliente.documento)
        .order_by(func.sum(Factura.saldo).desc())
        .all()
    )
    items = [
        FilaCartera(
            cliente_id=cid,
            nombre=nombre,
            documento=documento,
            facturas=int(n_fac),
            total=float(total),
            pagado=float(total) - float(saldo),
            saldo=float(saldo),
        )
        for cid, nombre, documento, n_fac, total, saldo in filas
    ]
    total_cartera = sum(i.saldo for i in items)
    return ReporteCartera(
        generado=get_colombia_time(),
        clientes_con_saldo=len(items),
        total_cartera=total_cartera,
        items=items,
    )


HEADER_CARTERA = ["Cliente", "Documento", "Facturas", "Total", "Pagado", "Saldo pendiente"]


def _filas_cartera(reporte: ReporteCartera) -> list[list]:
    return [
        [i.nombre, i.documento or "", i.facturas, i.total, i.pagado, i.saldo]
        for i in reporte.items
    ]


def _resumen_cartera(reporte: ReporteCartera) -> list[tuple[str, float | int]]:
    return [
        ("Clientes con saldo", reporte.clientes_con_saldo),
        ("Cartera total", reporte.total_cartera),
    ]


# ---------------------------------------------------------------- Caja / cierres


def _datos_caja(db: Session, desde: str | None, hasta: str | None) -> ReporteCaja:
    query = db.query(TurnoCaja).filter(TurnoCaja.abierta == False)  # noqa: E712
    inicio = _rango_desde(desde)
    fin = _rango_hasta(hasta)
    if inicio:
        query = query.filter(TurnoCaja.fecha_apertura >= inicio)
    if fin:
        query = query.filter(TurnoCaja.fecha_apertura < fin)
    turnos = query.order_by(TurnoCaja.id.desc()).all()

    items: list[FilaCierreCaja] = []
    saldo_inicial_total = 0.0
    entradas_total = 0.0
    salidas_total = 0.0
    saldo_final_total = 0.0
    acum_fp: dict[str, float] = {}

    for t in turnos:
        entradas = float(
            db.query(func.coalesce(func.sum(RegistroCaja.monto), 0.0))
            .filter(
                RegistroCaja.turno_caja_id == t.id,
                RegistroCaja.tipo == TipoMovimientoCaja.ENTRADA,
            )
            .scalar()
        )
        salidas = float(
            db.query(func.coalesce(func.sum(RegistroCaja.monto), 0.0))
            .filter(
                RegistroCaja.turno_caja_id == t.id,
                RegistroCaja.tipo == TipoMovimientoCaja.SALIDA,
            )
            .scalar()
        )
        esperado = t.saldo_inicial + entradas - salidas
        diferencia = (t.saldo_final_real - esperado) if t.saldo_final_real is not None else None
        saldo_inicial_total += t.saldo_inicial
        entradas_total += entradas
        salidas_total += salidas
        if t.saldo_final_real is not None:
            saldo_final_total += t.saldo_final_real

        for fp, monto in (
            db.query(RegistroCaja.forma_pago, func.coalesce(func.sum(RegistroCaja.monto), 0.0))
            .filter(
                RegistroCaja.turno_caja_id == t.id,
                RegistroCaja.tipo == TipoMovimientoCaja.ENTRADA,
            )
            .group_by(RegistroCaja.forma_pago)
            .all()
        ):
            clave = fp.value if hasattr(fp, "value") else str(fp)
            acum_fp[clave] = acum_fp.get(clave, 0.0) + float(monto)

        items.append(
            FilaCierreCaja(
                id=t.id,
                fecha_apertura=t.fecha_apertura,
                fecha_cierre=t.fecha_cierre,
                usuario_apertura=getattr(t.usuario_apertura, "nombre", None),
                usuario_cierre=getattr(t.usuario_cierre, "nombre", None),
                saldo_inicial=t.saldo_inicial,
                entradas=entradas,
                salidas=salidas,
                esperado=esperado,
                saldo_final_real=t.saldo_final_real,
                diferencia=diferencia,
            )
        )

    por_forma = [
        FormaPagoMonto(forma_pago=clave, monto=round(monto, 2))
        for clave, monto in sorted(acum_fp.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return ReporteCaja(
        desde=desde,
        hasta=hasta,
        generado=get_colombia_time(),
        turnos=len(turnos),
        saldo_inicial_total=saldo_inicial_total,
        entradas_total=entradas_total,
        salidas_total=salidas_total,
        esperado_total=saldo_inicial_total + entradas_total - salidas_total,
        saldo_final_total=saldo_final_total,
        diferencia_total=saldo_final_total - (saldo_inicial_total + entradas_total - salidas_total),
        por_forma_pago=por_forma,
        items=items,
    )


HEADER_CAJA = [
    "Turno",
    "Apertura",
    "Cierre",
    "Abrió",
    "Cerró",
    "Saldo inicial",
    "Entradas",
    "Salidas",
    "Esperado",
    "Saldo final real",
    "Diferencia",
]


def _filas_caja(reporte: ReporteCaja) -> list[list]:
    filas = []
    for i in reporte.items:
        filas.append(
            [
                i.id,
                i.fecha_apertura,
                i.fecha_cierre or "",
                i.usuario_apertura or "",
                i.usuario_cierre or "",
                i.saldo_inicial,
                i.entradas,
                i.salidas,
                i.esperado,
                i.saldo_final_real if i.saldo_final_real is not None else "",
                i.diferencia if i.diferencia is not None else "",
            ]
        )
    return filas


def _resumen_caja(reporte: ReporteCaja) -> list[tuple[str, float | int]]:
    return [
        ("Turnos cerrados", reporte.turnos),
        ("Saldo inicial total", reporte.saldo_inicial_total),
        ("Entradas totales", reporte.entradas_total),
        ("Salidas totales", reporte.salidas_total),
        ("Esperado total", reporte.esperado_total),
        ("Saldo final total", reporte.saldo_final_total),
    ]


# ---------------------------------------------------------------- Inventario


def _datos_inventario(db: Session) -> ReporteInventario:
    productos = db.query(Producto).order_by(Producto.nombre.asc()).all()
    items = [
        FilaInventario(
            id=p.id,
            codigo=p.codigo,
            nombre=p.nombre,
            precio=float(p.precio),
            stock=int(p.stock),
            valor=float(p.precio) * int(p.stock),
        )
        for p in productos
    ]
    return ReporteInventario(
        generado=get_colombia_time(),
        productos=len(items),
        unidades_totales=sum(i.stock for i in items),
        valor_inventario=sum(i.valor for i in items),
        items=items,
    )


HEADER_INVENTARIO = ["Código", "Producto", "Precio", "Stock", "Valor"]


def _filas_inventario(reporte: ReporteInventario) -> list[list]:
    return [
        [i.codigo, i.nombre, i.precio, i.stock, i.valor]
        for i in reporte.items
    ]


def _resumen_inventario(reporte: ReporteInventario) -> list[tuple[str, float | int]]:
    return [
        ("Productos", reporte.productos),
        ("Unidades en inventario", reporte.unidades_totales),
        ("Valor del inventario", reporte.valor_inventario),
    ]


# ---------------------------------------------------------------- Endpoints (JSON)


@router.get("/ventas", response_model=ReporteVentas)
def reporte_ventas(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return _datos_ventas(db, desde, hasta)


@router.get("/top-productos", response_model=ReporteTopProductos)
def reporte_top_productos(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    limite: int = LIMITE_TOP,
    db: Session = Depends(get_db),
):
    return _datos_top(db, desde, hasta, max(1, min(limite, 200)))


@router.get("/cartera", response_model=ReporteCartera)
def reporte_cartera(db: Session = Depends(get_db)):
    return _datos_cartera(db)


@router.get("/caja", response_model=ReporteCaja)
def reporte_caja(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return _datos_caja(db, desde, hasta)


@router.get("/inventario", response_model=ReporteInventario)
def reporte_inventario(db: Session = Depends(get_db)):
    return _datos_inventario(db)


# ---------------------------------------------------------------- Endpoints (export)


def _archivo(
    contenido: bytes,
    nombre: str,
    formato: str,
):
    if formato == "excel":
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    elif formato == "pdf":
        media = "application/pdf"
        ext = "pdf"
    else:
        raise HTTPException(status_code=400, detail="Formato inválido: usa 'excel' o 'pdf'")
    filename = f"{nombre}.{ext}"
    return StreamingResponse(
        iter([contenido]),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cabeceras(reporte, desde: Optional[str], hasta: Optional[str]) -> str:
    if desde and hasta:
        return f"Período: {desde} a {hasta}"
    if desde:
        return f"Desde: {desde}"
    if hasta:
        return f"Hasta: {hasta}"
    return "Sin filtro de fechas"


def _exportar_dos_formatos(
    titulo: str,
    subtitulo: str,
    header: list[str],
    filas: list[list],
    money_cols,
    resumen: list[tuple],
    base_nombre: str,
    formato: str,
):
    if formato == "excel":
        contenido = excel_reporte(
            titulo,
            subtitulo,
            [
                {
                    "nombre": titulo,
                    "resumen": resumen,
                    "header": header,
                    "rows": filas,
                    "money_cols": money_cols,
                }
            ],
        )
    else:
        contenido = pdf_reporte(
            titulo,
            subtitulo,
            header,
            filas,
            money_cols=money_cols,
            horizontal=len(header) > 6,
        )
    return _archivo(contenido, base_nombre, formato)


@router.get("/ventas/exportar")
def exportar_ventas(
    formato: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    reporte = _datos_ventas(db, desde, hasta)
    return _exportar_dos_formatos(
        "Reporte de ventas",
        _cabeceras(reporte, desde, hasta),
        HEADER_VENTAS,
        _filas_ventas(reporte),
        {5, 6},
        _resumen_ventas(reporte),
        "ventas",
        formato,
    )


@router.get("/top-productos/exportar")
def exportar_top(
    formato: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    reporte = _datos_top(db, desde, hasta, LIMITE_TOP)
    return _exportar_dos_formatos(
        "Productos más vendidos",
        _cabeceras(reporte, desde, hasta),
        HEADER_TOP,
        _filas_top(reporte),
        {3, 4},
        _resumen_top(reporte),
        "top-productos",
        formato,
    )


@router.get("/cartera/exportar")
def exportar_cartera(formato: str, db: Session = Depends(get_db)):
    reporte = _datos_cartera(db)
    return _exportar_dos_formatos(
        "Estado de cartera",
        "Clientes con saldo pendiente",
        HEADER_CARTERA,
        _filas_cartera(reporte),
        {2, 3, 4, 5},
        _resumen_cartera(reporte),
        "cartera",
        formato,
    )


@router.get("/caja/exportar")
def exportar_caja(
    formato: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    reporte = _datos_caja(db, desde, hasta)
    return _exportar_dos_formatos(
        "Cierre de caja",
        _cabeceras(reporte, desde, hasta),
        HEADER_CAJA,
        _filas_caja(reporte),
        {5, 6, 7, 8, 9, 10},
        _resumen_caja(reporte),
        "cierre-caja",
        formato,
    )


@router.get("/inventario/exportar")
def exportar_inventario(formato: str, db: Session = Depends(get_db)):
    reporte = _datos_inventario(db)
    return _exportar_dos_formatos(
        "Inventario",
        "Stock y valorización del catálogo",
        HEADER_INVENTARIO,
        _filas_inventario(reporte),
        {2, 4},
        _resumen_inventario(reporte),
        "inventario",
        formato,
    )