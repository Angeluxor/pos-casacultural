from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from fastapi import HTTPException
from app.db.models import (
    TurnoCaja,
    RegistroCaja,
    TipoMovimientoCaja,
    FormaPago,
    Factura,
    EstadoFactura,
    Usuario,
)
from app.schemas.caja import TurnoCajaCreate, TurnoCajaUpdate, RegistroCajaCreate, TurnoCajaHistorial
from app.core.timezone import get_colombia_time, BOGOTA_TZ
from app.core.orden import ordenar
from app.core.categorias_caja import (
    CATEGORIA_APERTURA,
    CATEGORIA_CIERRE,
    normalizar_categoria,
)

# El bolsillo "banco" agrupa todo lo que no entra al cajón físico.
FORMAS_BANCO = {FormaPago.TRANSFERENCIA, FormaPago.TARJETA, FormaPago.OTRO}

# Facturas con saldo por cobrar que, al cerrar la caja, pasan a Crédito.
ESTADOS_PENDIENTES_CIERRE = (EstadoFactura.ABIERTA, EstadoFactura.PAGADO_PARCIAL)


def facturas_pendientes_cierre(db: Session, turno_id: int):
    """Facturas del turno con saldo por cobrar (Abierta o Pagado Parcial)."""
    return (
        db.query(Factura)
        .filter(
            Factura.turno_caja_id == turno_id,
            Factura.estado.in_(ESTADOS_PENDIENTES_CIERRE),
            Factura.saldo > 0,
        )
        .order_by(Factura.id.asc())
        .all()
    )


def resumen_ventas_turno(db: Session, turno_id: int) -> dict:
    """Ventas facturadas del turno y cuánto queda a crédito (no cobrado).

    "Ventas" es todo lo facturado en el turno salvo lo anulado; "créditos" es el
    saldo por cobrar de esas facturas (lo que al cerrar la caja pasa a Crédito).
    El "cobrado" es la diferencia, es decir, el dinero que sí entró por ventas.
    """
    ventas = float(
        db.query(func.coalesce(func.sum(Factura.total), 0.0))
        .filter(
            Factura.turno_caja_id == turno_id,
            Factura.estado != EstadoFactura.ANULADA,
        )
        .scalar()
    )
    creditos = float(
        db.query(func.coalesce(func.sum(Factura.saldo), 0.0))
        .filter(
            Factura.turno_caja_id == turno_id,
            Factura.estado != EstadoFactura.ANULADA,
            Factura.saldo > 0,
        )
        .scalar()
    )
    return {
        "ventas": round(ventas, 2),
        "creditos": round(creditos, 2),
        "cobrado": round(ventas - creditos, 2),
    }


def forma_es_banco(forma_pago) -> bool:
    return forma_pago in FORMAS_BANCO


def resumen_movimientos(db: Session, turno_id: int) -> tuple[dict, dict]:
    """Suma las entradas y salidas del turno separadas por bolsillo (efectivo/banco)."""
    filas = (
        db.query(
            RegistroCaja.tipo,
            RegistroCaja.forma_pago,
            func.coalesce(func.sum(RegistroCaja.monto), 0.0),
        )
        .filter(
            RegistroCaja.turno_caja_id == turno_id,
            RegistroCaja.tipo.in_(
                [TipoMovimientoCaja.ENTRADA, TipoMovimientoCaja.SALIDA]
            ),
        )
        .group_by(RegistroCaja.tipo, RegistroCaja.forma_pago)
        .all()
    )
    entradas = {"efectivo": 0.0, "banco": 0.0}
    salidas = {"efectivo": 0.0, "banco": 0.0}
    for tipo, forma_pago, monto in filas:
        destino = entradas if tipo == TipoMovimientoCaja.ENTRADA else salidas
        destino["banco" if forma_es_banco(forma_pago) else "efectivo"] += float(monto)
    return entradas, salidas


def obtener_caja_abierta(db: Session):
    return db.query(TurnoCaja).filter(TurnoCaja.abierta == True).first()


def saldos_actuales(db: Session) -> dict:
    """Dinero disponible hoy en cada bolsillo de la caja.

    Si hay un turno abierto se usa el saldo esperado (inicial + entradas -
    salidas). Si no, se usan los saldos reales del último cierre; si nunca hubo
    caja, ambos quedan en cero.
    """
    turno = obtener_caja_abierta(db)
    if turno:
        entradas, salidas = resumen_movimientos(db, turno.id)
        return {
            "efectivo": round(
                turno.saldo_inicial_efectivo
                + entradas["efectivo"]
                - salidas["efectivo"],
                2,
            ),
            "banco": round(
                turno.saldo_inicial_banco + entradas["banco"] - salidas["banco"],
                2,
            ),
            "abierta": True,
            "turno_id": turno.id,
            "origen": f"Turno #{turno.id} abierto (saldo esperado)",
        }

    ultimo = (
        db.query(TurnoCaja)
        .filter(TurnoCaja.abierta == False)  # noqa: E712
        .order_by(TurnoCaja.fecha_cierre.desc(), TurnoCaja.id.desc())
        .first()
    )
    if not ultimo:
        return {
            "efectivo": 0.0,
            "banco": 0.0,
            "abierta": False,
            "turno_id": None,
            "origen": "Sin turnos de caja registrados",
        }

    entradas, salidas = resumen_movimientos(db, ultimo.id)
    efectivo = ultimo.saldo_final_real_efectivo
    banco = ultimo.saldo_final_real_banco
    if efectivo is None:
        efectivo = ultimo.saldo_inicial_efectivo + entradas["efectivo"] - salidas["efectivo"]
    if banco is None:
        banco = ultimo.saldo_inicial_banco + entradas["banco"] - salidas["banco"]
    return {
        "efectivo": round(float(efectivo), 2),
        "banco": round(float(banco), 2),
        "abierta": False,
        "turno_id": ultimo.id,
        "origen": f"Último cierre (turno #{ultimo.id})",
    }


def abrir_caja(db: Session, turno: TurnoCajaCreate, usuario_id: int):
    caja_abierta = obtener_caja_abierta(db)
    if caja_abierta:
        raise HTTPException(status_code=400, detail="Ya existe una caja abierta en este momento.")
    
    db_turno = TurnoCaja(
        usuario_apertura_id=usuario_id,
        saldo_inicial_efectivo=turno.saldo_inicial_efectivo,
        saldo_inicial_banco=turno.saldo_inicial_banco,
        abierta=True
    )
    db.add(db_turno)
    db.commit()
    db.refresh(db_turno)
    
    # Registrar cada saldo inicial como un movimiento de apertura (si es mayor a 0)
    for monto, forma_pago, detalle in (
        (turno.saldo_inicial_efectivo, FormaPago.EFECTIVO, "efectivo"),
        (turno.saldo_inicial_banco, FormaPago.TRANSFERENCIA, "banco"),
    ):
        if monto > 0:
            db.add(
                RegistroCaja(
                    turno_caja_id=db_turno.id,
                    usuario_id=usuario_id,
                    tipo=TipoMovimientoCaja.APERTURA,
                    referencia="Apertura de caja",
                    forma_pago=forma_pago,
                    monto=monto,
                    categoria=CATEGORIA_APERTURA,
                    observacion=f"Saldo inicial en {detalle} reportado al abrir caja",
                )
            )
    db.commit()
        
    return db_turno

def cerrar_caja(db: Session, turno_id: int, datos_cierre: TurnoCajaUpdate, usuario_id: int):
    db_turno = db.query(TurnoCaja).filter(TurnoCaja.id == turno_id).first()
    if not db_turno or not db_turno.abierta:
        raise HTTPException(status_code=400, detail="El turno de caja no existe o ya está cerrado.")

    # Pre-chequeo: las facturas del turno con saldo por cobrar pasan a Crédito,
    # pero no se puede cerrar si alguna es de un cliente eventual/temporal (no
    # tendría a quién cobrarle).
    pendientes = facturas_pendientes_cierre(db, turno_id)
    bloqueantes = [f for f in pendientes if not f.cliente or f.cliente.es_eventual]
    if bloqueantes:
        db.rollback()
        detalle = "; ".join(
            f"#{f.id} ({f.cliente_nombre or 'Cliente eventual'})" for f in bloqueantes
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede cerrar la caja: hay {len(bloqueantes)} factura(s) de "
                f"cliente eventual sin pagar ({detalle}). Asígnales un cliente real "
                "o cobra el saldo antes de cerrar."
            ),
        )
    for factura in pendientes:
        factura.estado = EstadoFactura.CREDITO

    db_turno.saldo_final_real_efectivo = datos_cierre.saldo_final_real_efectivo
    db_turno.saldo_final_real_banco = datos_cierre.saldo_final_real_banco
    db_turno.usuario_cierre_id = usuario_id
    db_turno.fecha_cierre = get_colombia_time()
    db_turno.abierta = False
    
    # Registrar el movimiento de cierre por cada bolsillo reportado.
    for monto, forma_pago, detalle in (
        (datos_cierre.saldo_final_real_efectivo, FormaPago.EFECTIVO, "efectivo"),
        (datos_cierre.saldo_final_real_banco, FormaPago.TRANSFERENCIA, "banco"),
    ):
        if monto > 0:
            db.add(
                RegistroCaja(
                    turno_caja_id=db_turno.id,
                    usuario_id=usuario_id,
                    tipo=TipoMovimientoCaja.CIERRE,
                    referencia="Cierre de caja",
                    forma_pago=forma_pago,
                    monto=monto,
                    categoria=CATEGORIA_CIERRE,
                    observacion=f"Saldo final reportado en {detalle} al cerrar caja",
                )
            )
    db.commit()
    
    return db_turno

def registrar_movimiento(db: Session, turno_id: int, movimiento: RegistroCajaCreate, usuario_id: int):
    # La nómina es una compensación, no un cobro: nunca debe registrarse como un
    # movimiento de caja (se contaría como efectivo). Se aplica desde la nómina
    # del usuario.
    if movimiento.forma_pago == FormaPago.NOMINA:
        raise HTTPException(
            status_code=400,
            detail="La forma de pago «Nómina» no se registra como movimiento de caja.",
        )
    if movimiento.tipo not in (
        TipoMovimientoCaja.ENTRADA,
        TipoMovimientoCaja.SALIDA,
    ):
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden registrar entradas y salidas manuales de caja.",
        )
    try:
        categoria = normalizar_categoria(movimiento.tipo, movimiento.categoria)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db_movimiento = RegistroCaja(
        turno_caja_id=turno_id,
        usuario_id=usuario_id,
        tipo=movimiento.tipo,
        referencia=movimiento.referencia,
        forma_pago=movimiento.forma_pago,
        monto=movimiento.monto,
        categoria=categoria,
        observacion=movimiento.observacion
    )
    db.add(db_movimiento)
    db.commit()
    db.refresh(db_movimiento)
    return db_movimiento

def obtener_movimientos(
    db: Session, turno_id: int, categoria: str | None = None
):
    query = db.query(RegistroCaja).filter(RegistroCaja.turno_caja_id == turno_id)
    if categoria:
        query = query.filter(RegistroCaja.categoria == categoria)
    return query.order_by(RegistroCaja.fecha.asc(), RegistroCaja.id.asc()).all()


def obtener_turnos(
    db: Session,
    skip: int = 0,
    limit: int = 30,
    desde: str | None = None,
    hasta: str | None = None,
    incluir_abierta: bool = False,
    orden: str | None = None,
    direccion: str | None = None,
):
    query = db.query(TurnoCaja)
    if not incluir_abierta:
        query = query.filter(TurnoCaja.abierta == False)
    if desde:
        try:
            d = date.fromisoformat(desde)
            query = query.filter(
                TurnoCaja.fecha_apertura >= datetime.combine(d, time.min, tzinfo=BOGOTA_TZ)
            )
        except ValueError:
            pass
    if hasta:
        try:
            h = date.fromisoformat(hasta)
            query = query.filter(
                TurnoCaja.fecha_apertura
                < datetime.combine(h + timedelta(days=1), time.min, tzinfo=BOGOTA_TZ)
            )
        except ValueError:
            pass

    columnas = {
        "id": TurnoCaja.id,
        "apertura": TurnoCaja.fecha_apertura,
        "cierre": TurnoCaja.fecha_cierre,
    }
    # Ordenar por "Abrió"/"Cerró" exige unir la tabla usuarios (con alias, porque
    # hay dos referencias al mismo modelo).
    if orden == "abrio":
        usuario_apertura = aliased(Usuario)
        query = query.outerjoin(
            usuario_apertura, TurnoCaja.usuario_apertura_id == usuario_apertura.id
        )
        columnas["abrio"] = usuario_apertura.nombre
    elif orden == "cerro":
        usuario_cierre = aliased(Usuario)
        query = query.outerjoin(
            usuario_cierre, TurnoCaja.usuario_cierre_id == usuario_cierre.id
        )
        columnas["cerro"] = usuario_cierre.nombre

    total = query.count()
    turnos = (
        ordenar(
            query,
            orden,
            direccion,
            columnas,
            [TurnoCaja.id.desc()],
            desempate=TurnoCaja.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    resultado: list[TurnoCajaHistorial] = []
    for t in turnos:
        entradas, salidas = resumen_movimientos(db, t.id)
        esperado_efectivo = t.saldo_inicial_efectivo + entradas["efectivo"] - salidas["efectivo"]
        esperado_banco = t.saldo_inicial_banco + entradas["banco"] - salidas["banco"]
        diferencia_efectivo = (
            (t.saldo_final_real_efectivo - esperado_efectivo)
            if t.saldo_final_real_efectivo is not None
            else None
        )
        diferencia_banco = (
            (t.saldo_final_real_banco - esperado_banco)
            if t.saldo_final_real_banco is not None
            else None
        )
        resultado.append(
            TurnoCajaHistorial(
                id=t.id,
                usuario_apertura_id=t.usuario_apertura_id,
                usuario_cierre_id=t.usuario_cierre_id,
                fecha_apertura=t.fecha_apertura,
                fecha_cierre=t.fecha_cierre,
                saldo_inicial_efectivo=t.saldo_inicial_efectivo,
                saldo_inicial_banco=t.saldo_inicial_banco,
                saldo_final_real_efectivo=t.saldo_final_real_efectivo,
                saldo_final_real_banco=t.saldo_final_real_banco,
                abierta=t.abierta,
                usuario_apertura_nombre=getattr(t.usuario_apertura, "nombre", None),
                usuario_cierre_nombre=getattr(t.usuario_cierre, "nombre", None),
                entradas_efectivo=entradas["efectivo"],
                entradas_banco=entradas["banco"],
                salidas_efectivo=salidas["efectivo"],
                salidas_banco=salidas["banco"],
                esperado_efectivo=esperado_efectivo,
                esperado_banco=esperado_banco,
                diferencia_efectivo=diferencia_efectivo,
                diferencia_banco=diferencia_banco,
            )
        )
    return total, resultado
