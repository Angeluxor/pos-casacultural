"""Cálculo de costos vigentes e históricos de los productos.

Fuentes de costo, en orden de prioridad:

1. **Receta**: si el producto es una preparación, su costo es la suma de los
   insumos (a costo vigente) dividida por el rendimiento.
2. **Costo manual**: el registro manual más reciente reemplaza al promedio.
3. **Compras**: promedio ponderado de las líneas de ingreso de inventario.

Las recetas pueden usar otras preparaciones como insumo (recetas anidadas).
La resolución detecta ciclos y los marca como incompletos, aunque el guardado
de recetas rechaza cualquier ciclo antes de persistirlo.

Este módulo también alimenta el Balance general: el inventario y el costo de
ventas de una preparación usan el costo calculado de su receta.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.timezone import BOGOTA_TZ, get_colombia_time
from app.db.models import (
    CostoManual,
    IngresoInventario,
    IngresoInventarioItem,
    Producto,
    Proveedor,
    Receta,
    RecetaItem,
)
from app.schemas.costos import CostoManualCreate, RecetaUpsert

SEMANAS_VENTANA = 6


@dataclass
class CostoVigente:
    costo: float
    origen: str


@dataclass
class PuntoCosto:
    fecha: datetime
    costo_unitario: float
    origen: str
    cantidad: Optional[float] = None
    proveedor: Optional[str] = None
    referencia: Optional[str] = None
    nota: Optional[str] = None


@dataclass
class ItemRecetaCalculado:
    producto: Producto
    cantidad: float
    costo_unitario: Optional[float]
    subtotal: Optional[float]
    origen: Optional[str]


@dataclass
class RecetaCalculada:
    costo_total: Optional[float]
    costo_unitario: Optional[float]
    completo: bool
    faltantes: List[str]
    items: List[ItemRecetaCalculado]


# ---------------------------------------------------------------------------
# Costo vigente
# ---------------------------------------------------------------------------


def promedio_compras(db: Session) -> Dict[int, float]:
    """Costo promedio ponderado por producto según las líneas de compra."""
    filas = (
        db.query(
            IngresoInventarioItem.producto_id,
            func.sum(
                IngresoInventarioItem.costo_unitario
                * IngresoInventarioItem.cantidad
            ),
            func.sum(IngresoInventarioItem.cantidad),
        )
        .filter(
            IngresoInventarioItem.producto_id.isnot(None),
            IngresoInventarioItem.costo_unitario.isnot(None),
            IngresoInventarioItem.cantidad.isnot(None),
            IngresoInventarioItem.cantidad > 0,
        )
        .group_by(IngresoInventarioItem.producto_id)
        .all()
    )
    costos: Dict[int, float] = {}
    for producto_id, valor_total, cantidad_total in filas:
        if cantidad_total:
            costos[int(producto_id)] = float(valor_total or 0.0) / float(
                cantidad_total
            )
    return costos


def manuales_vigentes(db: Session) -> Dict[int, CostoManual]:
    """Último costo manual de cada producto (por fecha y luego por id)."""
    filas = (
        db.query(CostoManual)
        .order_by(
            CostoManual.producto_id.asc(),
            CostoManual.fecha.desc(),
            CostoManual.id.desc(),
        )
        .all()
    )
    vigentes: Dict[int, CostoManual] = {}
    for fila in filas:
        vigentes.setdefault(int(fila.producto_id), fila)
    return vigentes


def recetas_por_producto(db: Session) -> Dict[int, Receta]:
    recetas = (
        db.query(Receta)
        .options(
            joinedload(Receta.producto),
            selectinload(Receta.items).joinedload(RecetaItem.producto),
        )
        .all()
    )
    return {int(receta.producto_id): receta for receta in recetas}


def costos_vigentes(db: Session) -> Dict[int, CostoVigente]:
    """Costo vigente de cada producto que tenga un costo calculable.

    Los productos sin compras, sin costo manual y sin receta no aparecen en el
    resultado. Una receta con insumos sin costo tampoco aparece: el Balance la
    sigue tratando como "sin costo" y la vista de Costos la marca incompleta.
    """
    promedios = promedio_compras(db)
    manuales = manuales_vigentes(db)
    recetas = recetas_por_producto(db)
    memo: Dict[int, Optional[CostoVigente]] = {}

    def resolver(producto_id: int, pila: Set[int]) -> Optional[CostoVigente]:
        if producto_id in memo:
            return memo[producto_id]
        if producto_id in pila:
            memo[producto_id] = None
            return None

        receta = recetas.get(producto_id)
        if receta is not None:
            total = 0.0
            completo = True
            for item in receta.items:
                sub = resolver(int(item.producto_id), pila | {producto_id})
                if sub is None:
                    completo = False
                    break
                total += sub.costo * float(item.cantidad or 0.0)
            rendimiento = float(receta.rendimiento or 0.0)
            if completo and rendimiento > 0:
                info: Optional[CostoVigente] = CostoVigente(
                    round(total / rendimiento, 2), "Receta"
                )
            else:
                info = None
        elif producto_id in manuales:
            info = CostoVigente(
                round(float(manuales[producto_id].costo_unitario or 0.0), 2),
                "Costo manual",
            )
        elif producto_id in promedios:
            info = CostoVigente(
                round(float(promedios[producto_id]), 2), "Costo promedio"
            )
        else:
            info = None

        memo[producto_id] = info
        return info

    ids = set(promedios) | set(manuales) | set(recetas)
    for producto_id in ids:
        resolver(int(producto_id), set())

    return {pid: info for pid, info in memo.items() if info is not None}


# ---------------------------------------------------------------------------
# Recetas
# ---------------------------------------------------------------------------


def _evaluar_receta(
    receta: Receta, costos: Dict[int, CostoVigente]
) -> RecetaCalculada:
    items: List[ItemRecetaCalculado] = []
    faltantes: List[str] = []
    total = 0.0
    completo = True

    for item in receta.items:
        info = costos.get(int(item.producto_id))
        cantidad = float(item.cantidad or 0.0)
        if info is None:
            completo = False
            faltantes.append(item.producto.nombre)
            items.append(
                ItemRecetaCalculado(item.producto, cantidad, None, None, None)
            )
        else:
            subtotal = round(info.costo * cantidad, 2)
            total += info.costo * cantidad
            items.append(
                ItemRecetaCalculado(
                    item.producto,
                    cantidad,
                    info.costo,
                    subtotal,
                    info.origen,
                )
            )

    rendimiento = float(receta.rendimiento or 0.0)
    if completo and rendimiento > 0:
        costo_total = round(total, 2)
        costo_unitario = round(total / rendimiento, 2)
    else:
        costo_total = None
        costo_unitario = None
        completo = False

    return RecetaCalculada(
        costo_total=costo_total,
        costo_unitario=costo_unitario,
        completo=completo,
        faltantes=faltantes,
        items=items,
    )


def _datos_receta(receta: Receta, calc: RecetaCalculada) -> dict:
    producto = receta.producto
    precio = float(producto.precio or 0.0)
    cmv_pct = margen = margen_pct = None
    if calc.costo_unitario is not None and precio > 0:
        cmv_pct = round(calc.costo_unitario / precio * 100, 2)
        margen = round(precio - calc.costo_unitario, 2)
        margen_pct = round(margen / precio * 100, 2)

    return {
        "producto_id": producto.id,
        "codigo": producto.codigo,
        "nombre": producto.nombre,
        "precio": precio,
        "rendimiento": float(receta.rendimiento or 0.0),
        "notas": receta.notas,
        "costo_total": calc.costo_total,
        "costo_unitario": calc.costo_unitario,
        "completo": calc.completo,
        "faltantes": calc.faltantes,
        "cmv_pct": cmv_pct,
        "margen": margen,
        "margen_pct": margen_pct,
        "items": [
            {
                "producto_id": item.producto.id,
                "codigo": item.producto.codigo,
                "nombre": item.producto.nombre,
                "cantidad": item.cantidad,
                "costo_unitario": item.costo_unitario,
                "subtotal": item.subtotal,
                "origen": item.origen,
            }
            for item in calc.items
        ],
    }


def listar_recetas(db: Session) -> List[dict]:
    recetas = (
        db.query(Receta)
        .options(
            joinedload(Receta.producto),
            selectinload(Receta.items).joinedload(RecetaItem.producto),
        )
        .all()
    )
    costos = costos_vigentes(db)
    filas = [
        _datos_receta(receta, _evaluar_receta(receta, costos))
        for receta in recetas
    ]
    filas.sort(key=lambda fila: fila["nombre"].lower())
    return filas


def obtener_receta(db: Session, producto_id: int) -> dict:
    receta = (
        db.query(Receta)
        .options(
            joinedload(Receta.producto),
            selectinload(Receta.items).joinedload(RecetaItem.producto),
        )
        .filter(Receta.producto_id == producto_id)
        .first()
    )
    if not receta:
        raise HTTPException(
            status_code=404, detail="El producto no tiene una receta registrada"
        )
    costos = costos_vigentes(db)
    return _datos_receta(receta, _evaluar_receta(receta, costos))


def _alcanza(
    grafo: Dict[int, List[int]], desde: int, objetivo: int, visitados: Set[int]
) -> bool:
    if desde == objetivo:
        return True
    if desde in visitados:
        return False
    visitados.add(desde)
    for siguiente in grafo.get(desde, []):
        if _alcanza(grafo, siguiente, objetivo, visitados):
            return True
    return False


def guardar_receta(db: Session, producto_id: int, datos: RecetaUpsert) -> dict:
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if float(datos.rendimiento) <= 0:
        raise HTTPException(
            status_code=400, detail="El rendimiento debe ser mayor a cero."
        )
    if not datos.items:
        raise HTTPException(
            status_code=400, detail="Agrega al menos un insumo a la receta."
        )

    ids_insumos = [int(item.producto_id) for item in datos.items]
    if len(ids_insumos) != len(set(ids_insumos)):
        raise HTTPException(
            status_code=400,
            detail="No repitas el mismo insumo en la receta.",
        )
    if producto_id in ids_insumos:
        raise HTTPException(
            status_code=400,
            detail="Una preparación no puede usarse a sí misma como insumo.",
        )

    existentes = (
        db.query(Producto.id).filter(Producto.id.in_(ids_insumos)).all()
        if ids_insumos
        else []
    )
    if len(existentes) != len(ids_insumos):
        raise HTTPException(
            status_code=400,
            detail="Alguno de los insumos no existe.",
        )

    # Detectar ciclos con el grafo actual de recetas, reemplazando la receta
    # que se está guardando por los nuevos insumos.
    recetas = recetas_por_producto(db)
    grafo = {
        int(pid): [int(item.producto_id) for item in receta.items]
        for pid, receta in recetas.items()
    }
    grafo[producto_id] = ids_insumos
    for insumo_id in ids_insumos:
        if _alcanza(grafo, insumo_id, producto_id, set()):
            raise HTTPException(
                status_code=400,
                detail=(
                    "La receta genera un ciclo: uno de los insumos depende, "
                    "directa o indirectamente, de esta preparación."
                ),
            )

    receta = (
        db.query(Receta).filter(Receta.producto_id == producto_id).first()
    )
    if not receta:
        receta = Receta(producto_id=producto_id)
        db.add(receta)
        db.flush()

    receta.rendimiento = float(datos.rendimiento)
    receta.notas = (datos.notas or "").strip() or None

    # Borrar los ítems anteriores antes de insertar los nuevos para no chocar
    # con la restricción única (receta_id, producto_id).
    receta.items.clear()
    db.flush()
    for item in datos.items:
        receta.items.append(
            RecetaItem(
                producto_id=int(item.producto_id),
                cantidad=float(item.cantidad),
            )
        )

    db.commit()
    db.refresh(receta)
    return obtener_receta(db, producto_id)


def eliminar_receta(db: Session, producto_id: int) -> None:
    receta = (
        db.query(Receta).filter(Receta.producto_id == producto_id).first()
    )
    if not receta:
        raise HTTPException(
            status_code=404, detail="El producto no tiene una receta registrada"
        )
    db.delete(receta)
    db.commit()


# ---------------------------------------------------------------------------
# Costos manuales
# ---------------------------------------------------------------------------


def _datos_manual(costo: CostoManual) -> dict:
    return {
        "id": costo.id,
        "producto_id": costo.producto_id,
        "producto_codigo": costo.producto.codigo,
        "producto_nombre": costo.producto.nombre,
        "fecha": costo.fecha,
        "costo_unitario": float(costo.costo_unitario),
        "nota": costo.nota,
        "usuario_id": costo.usuario_id,
        "usuario_nombre": costo.usuario.nombre if costo.usuario else None,
    }


def crear_costo_manual(
    db: Session, datos: CostoManualCreate, usuario_id: int
) -> dict:
    producto = db.query(Producto).filter(Producto.id == datos.producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if producto.receta is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "El producto tiene una receta: su costo se calcula desde los "
                "insumos. Edita la receta o elimínala para usar un costo manual."
            ),
        )

    if datos.fecha:
        fecha = datetime.combine(datos.fecha, time.min, tzinfo=BOGOTA_TZ)
    else:
        fecha = get_colombia_time()

    costo = CostoManual(
        producto_id=producto.id,
        fecha=fecha,
        costo_unitario=float(datos.costo_unitario),
        nota=(datos.nota or "").strip() or None,
        usuario_id=usuario_id,
    )
    db.add(costo)
    db.commit()
    db.refresh(costo)
    return _datos_manual(costo)


def listar_costos_manuales(
    db: Session, producto_id: Optional[int] = None, limit: int = 500
) -> List[dict]:
    query = db.query(CostoManual).options(
        joinedload(CostoManual.producto),
        joinedload(CostoManual.usuario),
    )
    if producto_id is not None:
        query = query.filter(CostoManual.producto_id == producto_id)
    filas = (
        query.order_by(CostoManual.fecha.desc(), CostoManual.id.desc())
        .limit(limit)
        .all()
    )
    return [_datos_manual(fila) for fila in filas]


def eliminar_costo_manual(db: Session, costo_id: int) -> None:
    costo = db.query(CostoManual).filter(CostoManual.id == costo_id).first()
    if not costo:
        raise HTTPException(status_code=404, detail="Costo manual no encontrado")
    db.delete(costo)
    db.commit()


# ---------------------------------------------------------------------------
# Histórico y resumen
# ---------------------------------------------------------------------------


def _inicio_dia(fecha: date) -> datetime:
    return datetime.combine(fecha, time.min, tzinfo=BOGOTA_TZ)


def historial_producto(
    db: Session,
    producto_id: int,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> List[dict]:
    desde_dt = _inicio_dia(desde) if desde else None
    hasta_dt = _inicio_dia(hasta + timedelta(days=1)) if hasta else None
    puntos: List[dict] = []

    query = (
        db.query(
            IngresoInventario.fecha,
            IngresoInventarioItem.costo_unitario,
            IngresoInventarioItem.cantidad,
            IngresoInventario.id,
            Proveedor.nombre,
        )
        .join(
            IngresoInventario,
            IngresoInventario.id == IngresoInventarioItem.ingreso_id,
        )
        .outerjoin(Proveedor, Proveedor.id == IngresoInventario.proveedor_id)
        .filter(
            IngresoInventarioItem.producto_id == producto_id,
            IngresoInventarioItem.costo_unitario.isnot(None),
            IngresoInventarioItem.cantidad.isnot(None),
            IngresoInventarioItem.cantidad > 0,
        )
    )
    if desde_dt:
        query = query.filter(IngresoInventario.fecha >= desde_dt)
    if hasta_dt:
        query = query.filter(IngresoInventario.fecha < hasta_dt)

    for fecha, costo, cantidad, ingreso_id, proveedor in query.all():
        puntos.append(
            {
                "fecha": fecha,
                "costo_unitario": float(costo),
                "origen": "Compra",
                "cantidad": float(cantidad),
                "proveedor": proveedor,
                "referencia": f"Ingreso #{ingreso_id}",
                "nota": None,
            }
        )

    query_manual = db.query(CostoManual).filter(
        CostoManual.producto_id == producto_id
    )
    if desde_dt:
        query_manual = query_manual.filter(CostoManual.fecha >= desde_dt)
    if hasta_dt:
        query_manual = query_manual.filter(CostoManual.fecha < hasta_dt)
    for fila in query_manual.all():
        puntos.append(
            {
                "fecha": fila.fecha,
                "costo_unitario": float(fila.costo_unitario),
                "origen": "Manual",
                "cantidad": None,
                "proveedor": None,
                "referencia": "Costo manual",
                "nota": fila.nota,
            }
        )

    puntos.sort(key=lambda punto: (punto["fecha"], punto["origen"]), reverse=True)
    return puntos


def _puntos_ventana(db: Session, desde: datetime) -> Dict[int, List[PuntoCosto]]:
    puntos: Dict[int, List[PuntoCosto]] = {}

    query = (
        db.query(
            IngresoInventarioItem.producto_id,
            IngresoInventario.fecha,
            IngresoInventarioItem.costo_unitario,
            IngresoInventarioItem.cantidad,
            IngresoInventario.id,
            Proveedor.nombre,
        )
        .join(
            IngresoInventario,
            IngresoInventario.id == IngresoInventarioItem.ingreso_id,
        )
        .outerjoin(Proveedor, Proveedor.id == IngresoInventario.proveedor_id)
        .filter(
            IngresoInventario.fecha >= desde,
            IngresoInventarioItem.producto_id.isnot(None),
            IngresoInventarioItem.costo_unitario.isnot(None),
            IngresoInventarioItem.cantidad.isnot(None),
            IngresoInventarioItem.cantidad > 0,
        )
    )
    for producto_id, fecha, costo, cantidad, ingreso_id, proveedor in query.all():
        puntos.setdefault(int(producto_id), []).append(
            PuntoCosto(
                fecha=fecha,
                costo_unitario=float(costo),
                origen="Compra",
                cantidad=float(cantidad),
                proveedor=proveedor,
                referencia=f"Ingreso #{ingreso_id}",
            )
        )

    for fila in (
        db.query(CostoManual).filter(CostoManual.fecha >= desde).all()
    ):
        puntos.setdefault(int(fila.producto_id), []).append(
            PuntoCosto(
                fecha=fila.fecha,
                costo_unitario=float(fila.costo_unitario),
                origen="Manual",
                nota=fila.nota,
                referencia="Costo manual",
            )
        )

    for lista in puntos.values():
        lista.sort(key=lambda punto: (punto.fecha, punto.origen))
    return puntos


def _mejor_punto(puntos: List[PuntoCosto]) -> Optional[dict]:
    if not puntos:
        return None
    compras = [punto for punto in puntos if punto.origen == "Compra"]
    candidatos = compras or puntos
    mejor = min(candidatos, key=lambda punto: (punto.costo_unitario, punto.fecha))
    return {
        "costo": mejor.costo_unitario,
        "proveedor": mejor.proveedor,
        "fecha": mejor.fecha,
        "origen": mejor.origen,
    }


def _variacion(puntos: List[PuntoCosto]) -> Optional[float]:
    if len(puntos) < 2:
        return None
    ordenados = sorted(puntos, key=lambda punto: (punto.fecha, punto.origen))
    primero = ordenados[0].costo_unitario
    ultimo = ordenados[-1].costo_unitario
    if primero == 0:
        return None
    return round((ultimo - primero) / primero * 100, 2)


def resumen_costos(db: Session, buscar: Optional[str] = None) -> List[dict]:
    query = db.query(Producto)
    if buscar and buscar.strip():
        filtro = f"%{buscar.strip()}%"
        query = query.filter(
            Producto.nombre.ilike(filtro) | Producto.codigo.ilike(filtro)
        )
    productos = query.order_by(Producto.nombre.asc()).all()

    costos = costos_vigentes(db)
    recetas = recetas_por_producto(db)
    desde = get_colombia_time() - timedelta(weeks=SEMANAS_VENTANA)
    puntos_ventana = _puntos_ventana(db, desde)

    filas: List[dict] = []
    for producto in productos:
        info = costos.get(producto.id)
        receta = recetas.get(producto.id)
        if receta is not None:
            calc = _evaluar_receta(receta, costos)
            completo = calc.completo
            faltantes = calc.faltantes
        else:
            completo = info is not None
            faltantes = []

        puntos = puntos_ventana.get(producto.id, [])
        mejor = _mejor_punto(puntos)
        variacion = _variacion(puntos)
        unidad_1a1 = producto.misma_unidad_compra_venta is not False
        mostrar_cmv = receta is not None or unidad_1a1
        precio = float(producto.precio or 0.0)

        cmv_pct = margen = margen_pct = None
        if mostrar_cmv and info is not None and precio > 0:
            cmv_pct = round(info.costo / precio * 100, 2)
            margen = round(precio - info.costo, 2)
            margen_pct = round(margen / precio * 100, 2)

        filas.append(
            {
                "producto_id": producto.id,
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "precio": precio,
                "stock": int(producto.stock or 0),
                "misma_unidad_compra_venta": unidad_1a1,
                "tiene_receta": receta is not None,
                "mostrar_cmv": mostrar_cmv,
                "costo_vigente": info.costo if info else None,
                "origen_costo": info.origen if info else None,
                "costo_completo": completo,
                "faltantes": faltantes,
                "mejor_precio_6s": mejor["costo"] if mejor else None,
                "mejor_proveedor": mejor["proveedor"] if mejor else None,
                "mejor_fecha": mejor["fecha"] if mejor else None,
                "mejor_origen": mejor["origen"] if mejor else None,
                "variacion_6s": variacion,
                "puntos_6s": len(puntos),
                "cmv_pct": cmv_pct,
                "margen": margen,
                "margen_pct": margen_pct,
            }
        )

    return filas


def insumos_receta(db: Session) -> List[dict]:
    """Productos con su costo vigente, para el selector de insumos."""
    productos = db.query(Producto).order_by(Producto.nombre.asc()).all()
    costos = costos_vigentes(db)
    recetas = recetas_por_producto(db)

    filas: List[dict] = []
    for producto in productos:
        info = costos.get(producto.id)
        receta = recetas.get(producto.id)
        if receta is not None:
            calc = _evaluar_receta(receta, costos)
            completo = calc.completo
            faltantes = calc.faltantes
        else:
            completo = info is not None
            faltantes = []

        filas.append(
            {
                "producto_id": producto.id,
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "precio": float(producto.precio or 0.0),
                "costo": info.costo if info else None,
                "origen": info.origen if info else None,
                "tiene_receta": receta is not None,
                "completo": completo,
                "faltantes": faltantes,
            }
        )

    return filas
