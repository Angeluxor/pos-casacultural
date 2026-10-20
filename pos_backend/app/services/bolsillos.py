"""Bolsillos virtuales para apartar dinero de gastos vitales.

El saldo de un bolsillo se calcula siempre desde sus movimientos:

    aportes - retiros

Los aportes no son salidas de caja: el dinero sigue en efectivo o banco, pero
deja de contar como disponible para la operación diaria. Los retiros vuelven a
dejar ese dinero disponible. Para pagar un gasto vital (por ejemplo, el
arriendo) se registra primero el retiro del bolsillo y luego la salida real en
Caja, o se usa la salida de caja y se libera el bolsillo; el sistema no crea
movimientos de caja automáticamente para evitar duplicar el gasto.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.crud import crud_caja
from app.core.timezone import get_colombia_time
from app.db.models import (
    Bolsillo,
    BolsilloMovimiento,
    TipoMovimientoBolsillo,
)
from app.schemas.bolsillos import BolsilloBalance

TOLERANCIA = 0.005


def _saldos_por_bolsillo(db: Session) -> dict[int, float]:
    """Saldo calculado de cada bolsillo (incluye archivados si tienen saldo)."""
    filas = (
        db.query(
            BolsilloMovimiento.bolsillo_id,
            BolsilloMovimiento.tipo,
            func.coalesce(func.sum(BolsilloMovimiento.monto), 0.0),
        )
        .group_by(BolsilloMovimiento.bolsillo_id, BolsilloMovimiento.tipo)
        .all()
    )
    saldos: dict[int, float] = {}
    for bolsillo_id, tipo, total in filas:
        delta = float(total)
        if tipo == TipoMovimientoBolsillo.RETIRO:
            delta = -delta
        saldos[int(bolsillo_id)] = round(
            saldos.get(int(bolsillo_id), 0.0) + delta, 2
        )
    return saldos


def total_reservado(db: Session) -> float:
    """Suma de los saldos de los bolsillos activos."""
    saldos = _saldos_por_bolsillo(db)
    ids_activos = [
        int(fila[0])
        for fila in db.query(Bolsillo.id)
        .filter(Bolsillo.activo == True)  # noqa: E712
        .all()
    ]
    return round(sum(saldos.get(i, 0.0) for i in ids_activos), 2)


def caja_disponible(db: Session) -> float:
    """Efectivo + banco menos lo reservado en bolsillos activos."""
    saldos = crud_caja.saldos_actuales(db)
    return round(
        float(saldos["efectivo"]) + float(saldos["banco"]) - total_reservado(db),
        2,
    )


def listar_bolsillos(
    db: Session, incluir_archivados: bool = False
) -> list[BolsilloBalance]:
    query = db.query(Bolsillo)
    if not incluir_archivados:
        query = query.filter(Bolsillo.activo == True)  # noqa: E712
    bolsillos = query.order_by(Bolsillo.nombre.asc()).all()
    saldos = _saldos_por_bolsillo(db)
    return [
        BolsilloBalance(
            id=b.id,
            nombre=b.nombre,
            descripcion=b.descripcion,
            reservado=round(saldos.get(b.id, 0.0), 2),
            fecha_creacion=b.fecha_creacion,
        )
        for b in bolsillos
    ]


def resumen_bolsillos(db: Session) -> tuple[float, list[BolsilloBalance]]:
    """Total reservado y detalle de los bolsillos activos."""
    items = listar_bolsillos(db)
    return round(sum(b.reservado for b in items), 2), items


def _obtener_activo(db: Session, bolsillo_id: int) -> Bolsillo:
    bolsillo = (
        db.query(Bolsillo)
        .filter(Bolsillo.id == bolsillo_id, Bolsillo.activo == True)  # noqa: E712
        .first()
    )
    if not bolsillo:
        raise HTTPException(
            status_code=404, detail="El bolsillo no existe o está archivado."
        )
    return bolsillo


def crear_bolsillo(
    db: Session, nombre: str, descripcion: Optional[str], usuario_id: int
) -> Bolsillo:
    nombre = (nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre del bolsillo es obligatorio.")
    if len(nombre) > 80:
        raise HTTPException(
            status_code=400, detail="El nombre no puede superar 80 caracteres."
        )
    existente = (
        db.query(Bolsillo)
        .filter(
            Bolsillo.activo == True,  # noqa: E712
            func.lower(Bolsillo.nombre) == nombre.lower(),
        )
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un bolsillo llamado «{existente.nombre}».",
        )

    bolsillo = Bolsillo(
        nombre=nombre,
        descripcion=(descripcion or "").strip() or None,
        activo=True,
        creado_por_id=usuario_id,
    )
    db.add(bolsillo)
    db.commit()
    db.refresh(bolsillo)
    return bolsillo


def archivar_bolsillo(db: Session, bolsillo_id: int) -> Bolsillo:
    bolsillo = _obtener_activo(db, bolsillo_id)
    saldo = round(_saldos_por_bolsillo(db).get(bolsillo.id, 0.0), 2)
    if abs(saldo) > TOLERANCIA:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede archivar un bolsillo con saldo reservado. "
                f"Libera primero {saldo:.2f}."
            ),
        )
    bolsillo.activo = False
    db.commit()
    db.refresh(bolsillo)
    return bolsillo


def registrar_movimiento(
    db: Session,
    bolsillo_id: int,
    tipo: TipoMovimientoBolsillo,
    monto: float,
    nota: Optional[str],
    usuario_id: int,
) -> BolsilloMovimiento:
    bolsillo = _obtener_activo(db, bolsillo_id)
    monto = round(float(monto), 2)
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0.")

    saldos = _saldos_por_bolsillo(db)
    saldo_actual = round(saldos.get(bolsillo.id, 0.0), 2)

    if tipo == TipoMovimientoBolsillo.RETIRO:
        if monto > saldo_actual + TOLERANCIA:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No puedes liberar más de lo reservado en el bolsillo. "
                    f"Saldo actual: {saldo_actual:.2f}."
                ),
            )
    else:
        # Solo se puede apartar dinero que exista hoy en caja/banco.
        total = total_reservado(db)
        caja = crud_caja.saldos_actuales(db)
        disponible = round(
            float(caja["efectivo"]) + float(caja["banco"]) - total, 2
        )
        if monto > disponible + TOLERANCIA:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No hay suficiente efectivo/banco disponible para apartar. "
                    f"Disponible: {disponible:.2f}."
                ),
            )

    movimiento = BolsilloMovimiento(
        bolsillo_id=bolsillo.id,
        tipo=tipo,
        monto=monto,
        nota=(nota or "").strip() or None,
        usuario_id=usuario_id,
        fecha=get_colombia_time(),
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)
    return movimiento


def historial_bolsillo(
    db: Session, bolsillo_id: int, limit: int = 200
) -> list[BolsilloMovimiento]:
    # Se permite consultar el historial de un bolsillo archivado.
    bolsillo = db.query(Bolsillo).filter(Bolsillo.id == bolsillo_id).first()
    if not bolsillo:
        raise HTTPException(status_code=404, detail="El bolsillo no existe.")
    return (
        db.query(BolsilloMovimiento)
        .options(joinedload(BolsilloMovimiento.usuario))
        .filter(BolsilloMovimiento.bolsillo_id == bolsillo_id)
        .order_by(BolsilloMovimiento.fecha.desc(), BolsilloMovimiento.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
