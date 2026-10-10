from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
from app.db.models import Cliente, Factura
from app.schemas.cliente import ClienteCreate, ClienteUpdate


def obtener_cliente_por_documento(db: Session, documento: str):
    return db.query(Cliente).filter(Cliente.documento == documento).first()


def obtener_cliente(db: Session, cliente_id: int):
    return db.query(Cliente).filter(Cliente.id == cliente_id).first()


def obtener_clientes(db: Session, skip: int = 0, limit: int = 100, buscar: Optional[str] = None):
    query = db.query(Cliente)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(
            Cliente.nombre.ilike(filtro)
            | Cliente.documento.ilike(filtro)
            | Cliente.celular.ilike(filtro)
            | Cliente.correo.ilike(filtro)
        )
    total = query.count()
    items = query.order_by(Cliente.nombre).offset(skip).limit(limit).all()
    return total, items


def crear_cliente(db: Session, cliente: ClienteCreate):
    db_cliente = Cliente(
        nombre=cliente.nombre,
        documento=cliente.documento,
        celular=cliente.celular,
        correo=cliente.correo,
    )
    db.add(db_cliente)
    db.commit()
    db.refresh(db_cliente)
    return db_cliente


def actualizar_cliente(db: Session, cliente_id: int, cliente_in: ClienteUpdate):
    cliente = obtener_cliente(db, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    for campo, valor in cliente_in.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)

    db.commit()
    db.refresh(cliente)
    return cliente


def eliminar_cliente(db: Session, cliente_id: int):
    cliente = obtener_cliente(db, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    tiene_facturas = db.query(Factura.id).filter(Factura.cliente_id == cliente_id).first()
    if tiene_facturas:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el cliente tiene facturas asociadas")

    db.delete(cliente)
    db.commit()
    return cliente
