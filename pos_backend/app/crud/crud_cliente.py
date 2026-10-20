from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import Optional
from app.db.models import Cliente, Factura, Usuario
from app.schemas.cliente import ClienteCreate, ClienteUpdate, ClienteFusion
from app.core.orden import ordenar

# Nombre del registro genérico que reemplaza al antiguo "Consumidor final".
CLIENTE_EVENTUAL_NOMBRE = "Cliente eventual"


def obtener_cliente_eventual(db: Session):
    return db.query(Cliente).filter(Cliente.es_eventual == True).first()


def obtener_o_crear_cliente_eventual(db: Session):
    """Devuelve el único registro "Cliente eventual", creándolo si no existe."""
    cliente = obtener_cliente_eventual(db)
    if cliente:
        return cliente
    cliente = Cliente(nombre=CLIENTE_EVENTUAL_NOMBRE, es_eventual=True)
    db.add(cliente)
    db.flush()
    return cliente


def obtener_cliente_por_documento(db: Session, documento: str):
    return db.query(Cliente).filter(Cliente.documento == documento).first()


def obtener_cliente(db: Session, cliente_id: int):
    return db.query(Cliente).filter(Cliente.id == cliente_id).first()


def obtener_clientes(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    buscar: Optional[str] = None,
    orden: Optional[str] = None,
    direccion: Optional[str] = None,
):
    # El cliente eventual es un registro de sistema: no se lista ni se elige.
    query = db.query(Cliente).filter(Cliente.es_eventual == False)
    if buscar:
        filtro = f"%{buscar.strip()}%"
        query = query.filter(
            Cliente.nombre.ilike(filtro)
            | Cliente.documento.ilike(filtro)
            | Cliente.celular.ilike(filtro)
            | Cliente.correo.ilike(filtro)
        )
    total = query.count()
    items = (
        ordenar(
            query,
            orden,
            direccion,
            {
                "nombre": Cliente.nombre,
                "documento": Cliente.documento,
                "celular": Cliente.celular,
                "correo": Cliente.correo,
            },
            [Cliente.nombre.asc(), Cliente.id.asc()],
            desempate=Cliente.id.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
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

    # El "Cliente eventual" es un registro del sistema que usan las ventas sin
    # cliente registrado; no debe poder eliminarse desde la UI ni por API.
    if cliente.es_eventual:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el cliente eventual: es un registro del sistema",
        )

    # Un cliente puede estar vinculado a un usuario para descontar nómina. Se
    # bloquea el borrado para no dejar al usuario sin su cliente sin avisar: el
    # admin debe desvincularlo primero.
    vinculado = (
        db.query(Usuario).filter(Usuario.cliente_id == cliente_id).first()
    )
    if vinculado:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede eliminar: el cliente está vinculado al usuario "
                f"«{vinculado.username}» para nómina. Desvincúlalo primero."
            ),
        )

    # Una factura es historial contable: si el cliente tiene ventas, se bloquea
    # el borrado en lugar de dejarlas huérfanas o perder su trazabilidad. Para
    # depurar duplicados existe `fusionar_clientes`, que mueve las ventas a un
    # cliente principal antes de borrar los registros sobrantes.
    facturas = db.query(Factura.id).filter(Factura.cliente_id == cliente_id).count()
    if facturas:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: el cliente tiene "
                f"{facturas} factura(s) asociada(s). "
                "Si es un duplicado, usa la fusión de clientes."
            ),
        )

    try:
        db.delete(cliente)
        db.commit()
    except IntegrityError:
        # Red de seguridad: si en el futuro otra tabla referencia clientes, la
        # FK de la base de datos lo impide y aquí se devuelve un error claro.
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar: el cliente tiene registros asociados "
                "(facturas u otros movimientos)."
            ),
        )
    return cliente


def _valor_unico(origenes, campo: str) -> Optional[str]:
    """Valor no vacío del campo, solo si todos los duplicados coinciden.

    Si los duplicados tienen valores distintos (p. ej. dos celulares
    diferentes), se devuelve ``None`` para no elegir uno al azar.
    """
    valores = {
        valor.strip()
        for cliente in origenes
        if (valor := getattr(cliente, campo)) and valor.strip()
    }
    return valores.pop() if len(valores) == 1 else None


def _completar_datos_desde_duplicados(db: Session, destino: Cliente, origenes, ids: set[int]) -> None:
    """Completa campos vacíos del cliente principal con datos inequívocos.

    El nombre nunca se toca: el admin decide cuál es el cliente que se conserva.
    """
    for campo in ("celular", "correo"):
        if getattr(destino, campo):
            continue
        valor = _valor_unico(origenes, campo)
        if valor:
            setattr(destino, campo, valor)

    if destino.documento:
        return
    documento = _valor_unico(origenes, "documento")
    if not documento:
        return
    # El documento es único: se evita chocar con otro cliente fuera de la fusión.
    existe = (
        db.query(Cliente.id)
        .filter(Cliente.documento == documento, Cliente.id.notin_(ids))
        .first()
    )
    if not existe:
        destino.documento = documento


def fusionar_clientes(db: Session, datos: ClienteFusion):
    """Consolida clientes duplicados en ``destino_id``.

    Reasigna todas las facturas de los orígenes al cliente principal y elimina
    los registros duplicados. Las facturas no se borran ni se modifican en sus
    importes: solo cambia el cliente al que quedan asociadas.
    """
    origen_ids = list(dict.fromkeys(datos.origen_ids))
    if datos.destino_id in origen_ids:
        raise HTTPException(
            status_code=400,
            detail="El cliente principal no puede estar entre los duplicados a eliminar",
        )

    ids = set(origen_ids) | {datos.destino_id}
    # Bloquea los clientes implicados para que no se creen ventas nuevas
    # mientras se mueven las facturas (PostgreSQL; en SQLite se ignora).
    clientes = (
        db.query(Cliente)
        .filter(Cliente.id.in_(ids))
        .with_for_update()
        .all()
    )
    por_id = {cliente.id: cliente for cliente in clientes}

    if datos.destino_id not in por_id:
        raise HTTPException(status_code=404, detail="Cliente principal no encontrado")
    faltantes = [cliente_id for cliente_id in origen_ids if cliente_id not in por_id]
    if faltantes:
        raise HTTPException(
            status_code=404,
            detail=f"Clientes no encontrados: {', '.join(map(str, faltantes))}",
        )

    destino = por_id[datos.destino_id]
    origenes = [por_id[cliente_id] for cliente_id in origen_ids]
    if destino.es_eventual or any(cliente.es_eventual for cliente in origenes):
        raise HTTPException(
            status_code=400,
            detail="El cliente eventual no se puede fusionar ni usar como cliente principal",
        )

    if datos.completar_datos:
        _completar_datos_desde_duplicados(db, destino, origenes, ids)

    # Vínculo de nómina: si un duplicado estaba vinculado a un usuario, el
    # vínculo debe quedar en el cliente principal. Solo se puede mover uno: la
    # relación es uno a uno y el destino debe estar libre.
    vinculados = (
        db.query(Usuario)
        .filter(Usuario.cliente_id.in_(origen_ids))
        .with_for_update()
        .all()
    )
    if vinculados:
        destino_ocupado = (
            db.query(Usuario).filter(Usuario.cliente_id == destino.id).first()
        )
        if destino_ocupado or len(vinculados) > 1:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pueden fusionar: hay usuarios de nómina vinculados a "
                    "estos clientes. Desvincula los usuarios implicados y vuelve "
                    "a intentarlo."
                ),
            )
        vinculados[0].cliente_id = destino.id

    try:
        facturas_reasignadas = (
            db.query(Factura)
            .filter(Factura.cliente_id.in_(origen_ids))
            .update({Factura.cliente_id: destino.id}, synchronize_session=False)
        )
        db.query(Cliente).filter(Cliente.id.in_(origen_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "No se pudo fusionar: se crearon facturas nuevas para algún "
                "duplicado mientras se realizaba la operación. Inténtalo de nuevo."
            ),
        )

    db.refresh(destino)
    return destino, facturas_reasignadas, len(origenes)
