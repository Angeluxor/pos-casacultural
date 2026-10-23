"""Balance general operativo y su exportación."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permiso
from app.db.models import Usuario
from app.db.session import get_db
from app.schemas.balance import BalanceGeneral
from app.schemas.bolsillos import (
    BolsilloBalance,
    BolsilloCrear,
    BolsilloMovimientoCrear,
    BolsilloMovimientoResponse,
)
from app.services import bolsillos
from app.services.balance import calcular_balance
from app.services.reportes_export import excel_reporte, pdf_reporte

router = APIRouter(dependencies=[Depends(require_permiso("balance.ver"))])


def _filas_balance(reporte: BalanceGeneral) -> list[list]:
    a, p = reporte.activos, reporte.pasivos
    return [
        ["ACTIVOS", ""],
        ["Efectivo", a.efectivo],
        ["Banco", a.banco],
        ["Reservado en bolsillos", a.reservado],
        ["Disponible para operación", a.disponible],
        ["Inventario", a.inventario],
        ["Cartera por cobrar", a.cartera],
        ["Total activos", a.total],
        ["", ""],
        ["PASIVOS", ""],
        ["Cuentas por pagar", p.cuentas_por_pagar],
        ["Total pasivos", p.total],
        ["", ""],
        ["PATRIMONIO", ""],
        ["Patrimonio (activos - pasivos)", reporte.patrimonio.total],
    ]


def _filas_bolsillos(reporte: BalanceGeneral) -> list[list]:
    return [
        [b.nombre, b.descripcion or "", b.reservado]
        for b in reporte.bolsillos
    ]


def _filas_resultados(reporte: BalanceGeneral) -> list[list]:
    r = reporte.resultados
    return [
        ["Ventas netas", r.ventas_netas],
        ["Costo de ventas", r.costo_ventas],
        ["Utilidad bruta", r.utilidad_bruta],
        ["Gastos de caja", r.gastos_caja],
        ["Otros gastos (ingresos no inventariables)", r.gastos_otros],
        ["Total gastos", r.gastos],
        ["Utilidad del período", r.utilidad],
        ["Margen", f"{r.margen:.2f}%"],
        ["Facturas del período", r.facturas],
    ]


def _filas_inventario(reporte: BalanceGeneral) -> list[list]:
    return [
        [
            i.codigo,
            i.nombre,
            i.stock,
            i.costo_unitario,
            i.valor,
            i.origen,
        ]
        for i in reporte.inventario
    ]


def _filas_cuentas(reporte: BalanceGeneral) -> list[list]:
    return [
        [
            c.fecha,
            c.proveedor or "",
            c.total,
            c.estado_ingreso,
        ]
        for c in reporte.cuentas_por_pagar
    ]


def _subtitulo(reporte: BalanceGeneral, desde: Optional[str], hasta: Optional[str]) -> str:
    corte = reporte.fecha_corte.strftime("%Y-%m-%d %H:%M")
    if desde and hasta:
        periodo = f"Resultados del {desde} al {hasta}"
    elif desde:
        periodo = f"Resultados desde {desde}"
    elif hasta:
        periodo = f"Resultados hasta {hasta}"
    else:
        periodo = "Resultados sin filtro de fechas"
    return f"Corte: {corte} · {periodo}"


def _archivo(contenido: bytes, nombre: str, formato: str):
    if formato == "excel":
        media = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        ext = "xlsx"
    elif formato == "pdf":
        media = "application/pdf"
        ext = "pdf"
    else:
        raise HTTPException(
            status_code=400, detail="Formato inválido: usa 'excel' o 'pdf'"
        )
    return StreamingResponse(
        iter([contenido]),
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}.{ext}"'
        },
    )


@router.get("", response_model=BalanceGeneral)
def obtener_balance(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return calcular_balance(db, desde=desde, hasta=hasta)


# --- Bolsillos de gastos vitales -------------------------------------------------


@router.get("/bolsillos", response_model=List[BolsilloBalance])
def listar_bolsillos(
    incluir_archivados: bool = False,
    db: Session = Depends(get_db),
):
    """Bolsillos activos (o todos) con su saldo reservado actual."""
    return bolsillos.listar_bolsillos(db, incluir_archivados=incluir_archivados)


@router.post("/bolsillos", response_model=BolsilloBalance)
def crear_bolsillo(
    datos: BolsilloCrear,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("balance.editar")),
):
    bolsillo = bolsillos.crear_bolsillo(
        db,
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        usuario_id=current_user.id,
        saldo_inicial=datos.saldo_inicial,
    )
    return BolsilloBalance(
        id=bolsillo.id,
        nombre=bolsillo.nombre,
        descripcion=bolsillo.descripcion,
        reservado=round(float(datos.saldo_inicial or 0.0), 2),
        saldo_inicial=round(float(datos.saldo_inicial or 0.0), 2),
        fecha_creacion=bolsillo.fecha_creacion,
    )


@router.post(
    "/bolsillos/{bolsillo_id}/movimientos",
    response_model=BolsilloMovimientoResponse,
)
def registrar_movimiento_bolsillo(
    bolsillo_id: int,
    datos: BolsilloMovimientoCrear,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("balance.editar")),
):
    return bolsillos.registrar_movimiento(
        db,
        bolsillo_id=bolsillo_id,
        tipo=datos.tipo,
        monto=datos.monto,
        nota=datos.nota,
        usuario_id=current_user.id,
        es_inicial=datos.es_inicial,
    )


@router.get(
    "/bolsillos/{bolsillo_id}/movimientos",
    response_model=List[BolsilloMovimientoResponse],
)
def historial_bolsillo(
    bolsillo_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    return bolsillos.historial_bolsillo(db, bolsillo_id, limit=limit)


@router.delete("/bolsillos/{bolsillo_id}", status_code=204)
def archivar_bolsillo(
    bolsillo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("balance.editar")),
):
    bolsillos.archivar_bolsillo(db, bolsillo_id)
    return None


@router.get("/exportar")
def exportar_balance(
    formato: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    reporte = calcular_balance(db, desde=desde, hasta=hasta)
    subtitulo = _subtitulo(reporte, desde, hasta)

    if formato == "excel":
        contenido = excel_reporte(
            "Balance general",
            subtitulo,
            [
                {
                    "nombre": "Balance",
                    "header": ["Concepto", "Valor"],
                    "rows": _filas_balance(reporte),
                    "money_cols": {1},
                },
                {
                    "nombre": "Bolsillos",
                    "header": ["Bolsillo", "Descripción", "Reservado"],
                    "rows": _filas_bolsillos(reporte),
                    "money_cols": {2},
                },
                {
                    "nombre": "Resultados",
                    "header": ["Concepto", "Valor"],
                    "rows": _filas_resultados(reporte),
                    "money_cols": {1},
                },
                {
                    "nombre": "Inventario",
                    "header": [
                        "Código",
                        "Producto",
                        "Stock",
                        "Costo unitario",
                        "Valor",
                        "Origen",
                    ],
                    "rows": _filas_inventario(reporte),
                    "money_cols": {3, 4},
                },
                {
                    "nombre": "Cuentas por pagar",
                    "header": ["Fecha", "Proveedor", "Total", "Estado"],
                    "rows": _filas_cuentas(reporte),
                    "money_cols": {2},
                },
            ],
        )
        return _archivo(contenido, "balance", formato)

    if formato == "pdf":
        filas = _filas_balance(reporte) + [["", ""]] + _filas_resultados(reporte)
        contenido = pdf_reporte(
            "Balance general",
            subtitulo,
            ["Concepto", "Valor"],
            filas,
            money_cols={1},
            horizontal=False,
        )
        return _archivo(contenido, "balance", formato)

    raise HTTPException(
        status_code=400, detail="Formato inválido: usa 'excel' o 'pdf'"
    )
