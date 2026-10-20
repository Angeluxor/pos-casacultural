from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.db.session import get_db
from app.db.models import Usuario, Cliente
from app.api.deps import require_permiso
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioResponse
from app.schemas.cliente import ClienteResponse
from app.schemas.nomina import (
    DeudaNominaResponse,
    DescuentoNominaCreate,
    DescuentoNominaResponse,
    HistorialNominaResponse,
)
from app.schemas.common import Pagina
from app.crud import crud_usuario, crud_nomina

router = APIRouter()

@router.post("/", response_model=UsuarioResponse)
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    db_user = crud_usuario.get_usuario_by_username(db, username=usuario.username)
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado")
    return crud_usuario.crear_usuario(db=db, usuario=usuario)

@router.get("/", response_model=Pagina[UsuarioResponse])
def leer_usuarios(skip: int = 0, limit: int = 50, buscar: Optional[str] = None, orden: Optional[str] = None, direccion: Optional[str] = None, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    total, items = crud_usuario.obtener_usuarios(db, skip=skip, limit=limit, buscar=buscar, orden=orden, direccion=direccion)
    return Pagina(items=items, total=total, skip=skip, limit=limit)

@router.get("/clientes-disponibles", response_model=list[ClienteResponse])
def clientes_disponibles(
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permiso("usuarios.gestionar")),
):
    """Clientes reales que se pueden vincular a un usuario (uno a uno).

    Devuelve los clientes sin usuario vinculado y, si se indica ``usuario_id``,
    también el que ya tiene ese usuario para poder conservarlo al editar.
    """
    query = (
        db.query(Cliente)
        .outerjoin(Usuario, Usuario.cliente_id == Cliente.id)
        .filter(Cliente.es_eventual == False)
        .filter(or_(Usuario.id.is_(None), Usuario.id == usuario_id))
        .order_by(Cliente.nombre.asc())
    )
    return query.limit(1000).all()


@router.get("/{user_id}", response_model=UsuarioResponse)
def leer_usuario(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    db_user = crud_usuario.get_usuario(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user


@router.get("/{user_id}/nomina", response_model=DeudaNominaResponse)
def leer_deuda_nomina(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("nomina.descontar"))):
    db_user = crud_usuario.get_usuario(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    cliente, facturas, saldo = crud_nomina.deuda_nomina(db, usuario=db_user)
    return DeudaNominaResponse(
        usuario_id=db_user.id,
        cliente_id=cliente.id,
        cliente_nombre=cliente.nombre,
        saldo_total=saldo,
        facturas=[
            {
                "factura_id": f.id,
                "fecha": f.fecha,
                "total": f.total,
                "saldo": f.saldo,
            }
            for f in facturas
        ],
    )


@router.get("/{user_id}/nomina/historial", response_model=HistorialNominaResponse)
def leer_historial_nomina(user_id: int, limite: int = 100, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("nomina.descontar"))):
    db_user = crud_usuario.get_usuario(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    cliente, saldo, descuentos, total, monto_total = crud_nomina.historial_nomina(
        db, usuario=db_user, limite=limite
    )
    return HistorialNominaResponse(
        usuario_id=db_user.id,
        usuario_nombre=db_user.nombre,
        cliente_id=cliente.id if cliente else None,
        cliente_nombre=cliente.nombre if cliente else None,
        saldo_total=saldo,
        descuentos=total,
        monto_total=round(monto_total, 2),
        items=[crud_nomina.fila_historial(d) for d in descuentos],
    )


@router.post("/{user_id}/nomina/descuento", response_model=DescuentoNominaResponse)
def aplicar_descuento_nomina(user_id: int, datos: DescuentoNominaCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("nomina.descontar"))):
    db_user = crud_usuario.get_usuario(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    descuento = crud_nomina.aplicar_descuento_nomina(
        db,
        usuario=db_user,
        monto=datos.monto,
        registrado_por=current_user,
        nota=datos.nota,
    )
    return DescuentoNominaResponse(
        descuento_id=descuento.id,
        usuario_id=db_user.id,
        cliente_id=descuento.cliente_id,
        cliente_nombre=descuento.cliente_nombre,
        monto_aplicado=descuento.monto,
        saldo_pendiente=descuento.saldo_pendiente,
        facturas_afectadas=descuento.facturas_afectadas,
        nota=descuento.nota,
    )

@router.put("/{user_id}", response_model=UsuarioResponse)
def actualizar_usuario(user_id: int, usuario: UsuarioUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    if usuario.activo is False and user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario")
    return crud_usuario.actualizar_usuario(db=db, user_id=user_id, usuario_in=usuario)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permiso("usuarios.gestionar"))):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")
    crud_usuario.eliminar_usuario(db=db, user_id=user_id)
    return None
