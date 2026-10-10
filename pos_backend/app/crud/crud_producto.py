from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
from app.db.models import Producto, Kardex, TipoMovimientoInventario
from app.schemas.producto import ProductoCreate, ProductoUpdate, KardexCreate

def obtener_producto_por_codigo(db: Session, codigo: str):
    return db.query(Producto).filter(Producto.codigo == codigo).first()

def obtener_producto(db: Session, producto_id: int):
    return db.query(Producto).filter(Producto.id == producto_id).first()

def obtener_productos(db: Session, skip: int = 0, limit: int = 100, buscar: Optional[str] = None):
    query = db.query(Producto)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(Producto.codigo.ilike(filtro) | Producto.nombre.ilike(filtro))
    total = query.count()
    items = query.order_by(Producto.nombre).offset(skip).limit(limit).all()
    return total, items

def registrar_kardex(db: Session, producto_id: int, kardex_data: KardexCreate, usuario_id: int):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    cantidad_movimiento = abs(kardex_data.cantidad)

    if kardex_data.tipo_movimiento == TipoMovimientoInventario.AJUSTE:
        if kardex_data.cantidad == 0:
            raise HTTPException(status_code=400, detail="El ajuste no puede ser 0.")
    elif kardex_data.cantidad <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad debe ser mayor a 0. Usa el tipo Ajuste para restar stock.",
        )

    # Actualizar stock del producto
    if kardex_data.tipo_movimiento in [TipoMovimientoInventario.ENTRADA_COMPRA, TipoMovimientoInventario.DEVOLUCION]:
        producto.stock += cantidad_movimiento
    elif kardex_data.tipo_movimiento == TipoMovimientoInventario.SALIDA_VENTA:
        if producto.stock < cantidad_movimiento:
            raise HTTPException(status_code=400, detail="Stock insuficiente para realizar la salida.")
        producto.stock -= cantidad_movimiento
    elif kardex_data.tipo_movimiento == TipoMovimientoInventario.AJUSTE:
        # En ajustes la cantidad recibida con su signo original aplica directo al cambio (-10 reduce 10, 10 aumenta 10)
        producto.stock += kardex_data.cantidad
        cantidad_movimiento = kardex_data.cantidad # Mantener el signo para el log

    db_kardex = Kardex(
        producto_id=producto_id,
        usuario_id=usuario_id,
        tipo_movimiento=kardex_data.tipo_movimiento,
        cantidad=cantidad_movimiento,
        saldo_stock=producto.stock,
        referencia=kardex_data.referencia
    )
    
    db.add(db_kardex)
    db.commit()
    db.refresh(db_kardex)
    return db_kardex

def crear_producto(db: Session, producto: ProductoCreate, usuario_id: int):
    db_producto = Producto(
        codigo=producto.codigo,
        nombre=producto.nombre,
        precio=producto.precio,
        stock=0 # Comienza en 0, el Kardex ajusta el stock real
    )
    db.add(db_producto)
    db.commit()
    db.refresh(db_producto)

    if producto.stock_inicial > 0:
        kardex_data = KardexCreate(
            tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
            cantidad=producto.stock_inicial,
            referencia="Stock inicial al crear producto",
            usuario_id=usuario_id
        )
        registrar_kardex(db, db_producto.id, kardex_data, usuario_id)
    else:
        # Refrescamos por si no entró al bloque anterior para asegurar que devolvemos el stock correcto
        db.refresh(db_producto)

    return db_producto

def obtener_kardex_producto(db: Session, producto_id: int):
    return db.query(Kardex).filter(Kardex.producto_id == producto_id).order_by(Kardex.fecha.desc()).all()


def actualizar_producto(db: Session, producto_id: int, producto_in: ProductoUpdate):
    producto = obtener_producto(db, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for campo, valor in producto_in.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)

    db.commit()
    db.refresh(producto)
    return producto
