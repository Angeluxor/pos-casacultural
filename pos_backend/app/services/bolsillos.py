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
    saldos, _ = _saldos_e_iniciales_por_bolsillo(db)
    return saldos


def _saldos_e_iniciales_por_bolsillo(
    db: Session,
) -> tuple[dict[int, float], dict[int, float]]:
    """Saldo total y parte aportada como saldo inicial, por bolsillo.

    El saldo inicial no salió de caja/banco: suma al bolsillo pero no reduce el
    disponible para operar. Por eso se calcula aparte de los aportes normales.
    """
    filas = (
        db.query(
            BolsilloMovimiento.bolsillo_id,
            BolsilloMovimiento.tipo,
            BolsilloMovimiento.es_inicial,
            func.coalesce(func.sum(BolsilloMovimiento.monto), 0.0),
        )
        .group_by(
            BolsilloMovimiento.bolsillo_id,
            BolsilloMovimiento.tipo,
            BolsilloMovimiento.es_inicial,
        )
        .all()
    )
    saldos: dict[int, float] = {}
    iniciales: dict[int, float] = {}
    for bolsillo_id, tipo, es_inicial, total in filas:
        bolsillo_id = int(bolsillo_id)
        monto = float(total)
        delta = -monto if tipo == TipoMovimientoBolsillo.RETIRO else monto
        saldos[bolsillo_id] = round(saldos.get(bolsillo_id, 0.0) + delta, 2)
        if es_inicial and tipo == TipoMovimientoBolsillo.APORTE:
            iniciales[bolsillo_id] = round(
                iniciales.get(bolsillo_id, 0.0) + monto, 2
            )
    return saldos, iniciales


def _ids_activos(db: Session) -> list[int]:
    return [
        int(fila[0])
        for fila in db.query(Bolsillo.id)
        .filter(Bolsillo.activo == True)  # noqa: E712
        .all()
    ]


def total_reservado(db: Session) -> float:
    """Suma de los saldos de los bolsillos activos."""
    saldos = _saldos_por_bolsillo(db)
    return round(sum(saldos.get(i, 0.0) for i in _ids_activos(db)), 2)


def total_saldo_inicial(db: Session) -> float:
    """Parte del reservado que no se descontó de caja/banco."""
    _, iniciales = _saldos_e_iniciales_por_bolsillo(db)
    return round(
        sum(iniciales.get(i, 0.0) for i in _ids_activos(db)), 2
    )


def reservado_de_caja(db: Session) -> float:
    """Reservado que sí salió del efectivo/banco disponible."""
    return round(total_reservado(db) - total_saldo_inicial(db), 2)


def caja_disponible(db: Session) -> float:
    """Efectivo + banco menos lo reservado que salió de la caja."""
    saldos = crud_caja.saldos_actuales(db)
    return round(
        float(saldos["efectivo"])
        + float(saldos["banco"])
        - reservado_de_caja(db),
        2,
    )


def listar_bolsillos(
    db: Session, incluir_archivados: bool = False
) -> list[BolsilloBalance]:
    query = db.query(Bolsillo)
    if not incluir_archivados:
        query = query.filter(Bolsillo.activo == True)  # noqa: E712
    bolsillos = query.order_by(Bolsillo.nombre.asc()).all()
    saldos, iniciales = _saldos_e_iniciales_por_bolsillo(db)
    return [
        BolsilloBalance(
            id=b.id,
            nombre=b.nombre,
            descripcion=b.descripcion,
            reservado=round(saldos.get(b.id, 0.0), 2),
            saldo_inicial=round(iniciales.get(b.id, 0.0), 2),
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
    db: Session,
    nombre: str,
    descripcion: Optional[str],
    usuario_id: int,
    saldo_inicial: float = 0.0,
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

    saldo_inicial = round(float(saldo_inicial or 0.0), 2)
    if saldo_inicial < 0:
        raise HTTPException(
            status_code=400, detail="El saldo inicial no puede ser negativo."
        )

    bolsillo = Bolsillo(
        nombre=nombre,
        descripcion=(descripcion or "").strip() or None,
        activo=True,
        creado_por_id=usuario_id,
    )
    db.add(bolsillo)
    db.flush()
    if saldo_inicial > 0:
        db.add(
            BolsilloMovimiento(
                bolsillo_id=bolsillo.id,
                tipo=TipoMovimientoBolsillo.APORTE,
                monto=saldo_inicial,
                nota="Saldo inicial",
                es_inicial=True,
                usuario_id=usuario_id,
                fecha=get_colombia_time(),
            )
        )
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
    es_inicial: bool = False,
) -> BolsilloMovimiento:
    bolsillo = _obtener_activo(db, bolsillo_id)
    monto = round(float(monto), 2)
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0.")
    if es_inicial and tipo != TipoMovimientoBolsillo.APORTE:
        raise HTTPException(
            status_code=400,
            detail="El saldo inicial solo se puede registrar como aporte.",
        )

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
    elif not es_inicial:
        # Solo se puede apartar dinero que exista hoy en caja/banco. El saldo
        # inicial es la excepción: representa dinero que ya estaba apartado
        # antes de usar la app y no se descuenta del banco.
        disponible = caja_disponible(db)
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
        es_inicial=es_inicial,
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
