from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.orden import ordenar
from app.db.models import IngresoInventario, Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate


def obtener_proveedor(db: Session, proveedor_id: int):
    return db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()


def obtener_proveedor_por_documento(db: Session, documento: str):
    return db.query(Proveedor).filter(Proveedor.documento == documento).first()


def obtener_proveedor_por_nombre(db: Session, nombre: str):
    """Busca por nombre sin distinguir mayúsculas ni espacios sobrantes."""
    return (
        db.query(Proveedor)
        .filter(func.lower(Proveedor.nombre) == nombre.strip().lower())
        .first()
    )


def obtener_proveedores(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    buscar: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
):
    query = db.query(Proveedor)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(
            Proveedor.nombre.ilike(filtro)
            | Proveedor.documento.ilike(filtro)
            | Proveedor.celular.ilike(filtro)
            | Proveedor.correo.ilike(filtro)
        )
    total = query.count()
    items = (
        ordenar(
            query,
            orden,
            direccion,
            {
                "nombre": Proveedor.nombre,
                "documento": Proveedor.documento,
                "celular": Proveedor.celular,
                "correo": Proveedor.correo,
            },
            [Proveedor.nombre.asc(), Proveedor.id.asc()],
            desempate=Proveedor.id.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return total, items


def crear_proveedor(db: Session, datos: ProveedorCreate):
    proveedor = Proveedor(
        nombre=datos.nombre,
        documento=datos.documento,
        celular=datos.celular,
        correo=datos.correo,
    )
    db.add(proveedor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Ya existe un proveedor con este documento",
        )
    db.refresh(proveedor)
    return proveedor


def actualizar_proveedor(db: Session, proveedor_id: int, datos: ProveedorUpdate):
    proveedor = obtener_proveedor(db, proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(proveedor, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Ya existe otro proveedor con este documento",
        )
    db.refresh(proveedor)
    return proveedor


def eliminar_proveedor(db: Session, proveedor_id: int):
    proveedor = obtener_proveedor(db, proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Los ingresos son historial contable: se conserva el proveedor mientras
    # tenga compras asociadas para no perder la trazabilidad.
    ingresos = (
        db.query(IngresoInventario.id)
        .filter(IngresoInventario.proveedor_id == proveedor_id)
        .count()
    )
    if ingresos:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: el proveedor tiene "
                f"{ingresos} ingreso(s) asociado(s)."
            ),
        )

    db.delete(proveedor)
    db.commit()
    return proveedor


def resolver_proveedor(
    db: Session,
    proveedor_id: Optional[int] = None,
    nombre: Optional[str] = None,
):
    """Devuelve el proveedor de un ingreso, creándolo si llega solo el nombre.

    El nombre se acepta por compatibilidad con integraciones y para permitir
    crear un proveedor directamente desde el formulario de Ingresos.
    """
    if proveedor_id is not None:
        proveedor = obtener_proveedor(db, proveedor_id)
        if not proveedor:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return proveedor

    if nombre and nombre.strip():
        nombre = nombre.strip()
        proveedor = obtener_proveedor_por_nombre(db, nombre)
        if proveedor:
            return proveedor
        proveedor = Proveedor(nombre=nombre)
        db.add(proveedor)
        db.flush()
        return proveedor

    return None
